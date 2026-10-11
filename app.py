from __future__ import annotations

import hmac
import json
import os
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from promptlab.pipeline import make_llm, run_all, show_outputs
from promptlab.prompts import TECHNIQUES, build_prompt
from promptlab.sandbox import docker_available, evaluate_python_code
from promptlab.scoring import WEIGHT_PRESETS, pick_best, summarize
from promptlab.storage import delete_all_experiments, get_experiments, reserve_usage_slot, save_experiment
from promptlab.provider import SpecGenerationError
from promptlab.tasks import PRESET_TASKS, generate_shared_spec, spec_from_preset

load_dotenv()
st.set_page_config(page_title="PromptLab", page_icon="🧪", layout="wide")
def secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, os.getenv(name, default))
    except Exception:
        value = os.getenv(name, default)
    return str(value or "")


access_password = secret_or_env("PROMPTLAB_ACCESS_PASSWORD")
if not access_password:
    st.error("PromptLab is locked. Configure PROMPTLAB_ACCESS_PASSWORD in Streamlit Settings → Secrets before using this app.")
    st.caption("Do not expose a public app that can use your private API keys without access control.")
    st.stop()

if not st.session_state.get("promptlab_authenticated", False):
    st.title("PromptLab")
    attempts = int(st.session_state.get("promptlab_login_attempts", 0))
    if attempts >= 5:
        st.error("Too many incorrect attempts in this session. Start a new session or contact the app owner.")
        st.stop()
    with st.form("promptlab_login"):
        entered_password = st.text_input("App access password", type="password")
        submitted = st.form_submit_button("Unlock PromptLab", type="primary")
    if submitted:
        if hmac.compare_digest(entered_password, access_password):
            st.session_state["promptlab_authenticated"] = True
            st.session_state["promptlab_login_attempts"] = 0
            st.rerun()
        else:
            st.session_state["promptlab_login_attempts"] = attempts + 1
            st.error("Incorrect password.")
    st.stop()

st.title("🧪 PromptLab")
st.caption("Automatic Groq + Ollama comparison across prompt-engineering techniques for code generation.")

# Provider IDs and endpoints are fixed server-side; users cannot edit them in the UI.
GROQ_MODEL = secret_or_env("GROQ_MODEL", "openai/gpt-oss-20b")
OLLAMA_MODEL = secret_or_env("OLLAMA_MODEL", "gpt-oss:20b-cloud")
OLLAMA_BASE_URL = secret_or_env("OLLAMA_BASE_URL", "https://ollama.com/v1").rstrip("/")
groq_key = secret_or_env("GROQ_API_KEY")
ollama_url = urlparse(OLLAMA_BASE_URL)
ollama_is_loopback = ollama_url.scheme == "http" and ollama_url.hostname in {"localhost", "127.0.0.1", "::1"}
ollama_url_valid = bool(ollama_url.hostname) and (ollama_url.scheme == "https" or ollama_is_loopback)
ollama_key = secret_or_env("OLLAMA_API_KEY", "ollama" if ollama_is_loopback else "")

try:
    RUNS_PER_HOUR = max(1, min(int(secret_or_env("PROMPTLAB_MAX_RUNS_PER_HOUR", "6")), 30))
except ValueError:
    RUNS_PER_HOUR = 6

docker_opt_in = secret_or_env("PROMPTLAB_ENABLE_DOCKER_EXECUTION", "false").strip().lower() == "true"
docker_ready = docker_opt_in and docker_available()
EXEC_MODES = {"AI estimate by Groq (does not execute code)": "ai"}
if docker_ready:
    EXEC_MODES["Docker sandbox (admin enabled)"] = "docker"



def safe_csv(frame: pd.DataFrame) -> str:
    """Escape formula-like text cells before users open exported CSV files in spreadsheet software."""
    safe = frame.copy()
    for column in safe.select_dtypes(include=["object", "string"]).columns:
        safe[column] = safe[column].map(
            lambda value: "'" + value
            if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@"))
            else value
        )
    return safe.to_csv(index=False)

def redact_error(value: object) -> str:
    message = str(value)
    for secret in (groq_key, ollama_key, access_password):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message[:700]

with st.sidebar:
    st.header("Connected models")
    st.success("Groq configured" if groq_key else "Missing GROQ_API_KEY")
    st.success("Ollama configured" if ollama_key else "Missing OLLAMA_API_KEY")
    st.caption("Both models run automatically. API keys are never displayed.")
    st.caption(f"Groq model: {GROQ_MODEL}")
    st.caption(f"Ollama model: {OLLAMA_MODEL}")
    st.header("Experiment settings")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.0, 0.1)
    exec_label = st.selectbox(
        "Test evaluator",
        list(EXEC_MODES),
        index=0,
        help="AI estimate is the safe hosted default. Actual execution is available only in Docker when enabled by the app owner.",
    )
    exec_mode = EXEC_MODES[exec_label]
    trials = st.slider("Trials per technique per model", 1, 3, 1)
    priority = st.selectbox("Best-response scoring", list(WEIGHT_PRESETS))
    st.caption(f"Quota: up to {RUNS_PER_HOUR} comparisons per rolling hour on this app instance.")
    if not docker_ready:
        st.caption("Docker execution is disabled; host-local Python execution is not offered in the web UI.")
    if st.button("Lock this session"):
        st.session_state["promptlab_authenticated"] = False
        st.session_state.pop("last_run", None)
        st.rerun()


def evaluator():
    return lambda code, fn, tests: evaluate_python_code(
        code,
        fn,
        tests,
        mode=exec_mode,
        groq_api_key=groq_key,
        groq_model=secret_or_env("GROQ_TEST_MODEL", GROQ_MODEL),
    )


llms = {
    "Groq": make_llm("Groq", groq_key, GROQ_MODEL, temperature),
    "Ollama": make_llm("Custom OpenAI-compatible", ollama_key, OLLAMA_MODEL, temperature, OLLAMA_BASE_URL),
}
model_names = {"Groq": GROQ_MODEL, "Ollama": OLLAMA_MODEL}

tab_run, tab_history, tab_method = st.tabs(["⚡ Prompt Lab", "History & analysis", "Research protocol"])

with tab_run:
    source = st.radio("Task source", ["One-line request", "Preset benchmark task"], horizontal=True)
    request = ""
    if source == "One-line request":
        request = st.text_input(
            "Describe the code you want in one line",
            placeholder="e.g. find the second largest number in a list without sorting", max_chars=500,
        )
    else:
        preset = st.selectbox("Benchmark task", list(PRESET_TASKS))
    selected = st.multiselect("Prompt techniques", [t.name for t in TECHNIQUES], default=[t.name for t in TECHNIQUES])
    ready = bool(groq_key and ollama_key and ollama_url_valid and selected and (request.strip() or source != "One-line request"))
    if not groq_key or not ollama_key:
        st.info("Add both GROQ_API_KEY and OLLAMA_API_KEY in Streamlit Settings → Secrets. The keys stay hidden.")
    if not ollama_url_valid:
        st.error("OLLAMA_BASE_URL must use HTTPS. HTTP is allowed only for a localhost Ollama server in local development.")
    go = st.button("Run Groq + Ollama comparison", type="primary", disabled=not ready)
    if go:
        try:
            allowed, _remaining = reserve_usage_slot(RUNS_PER_HOUR)
        except Exception:
            allowed = False
        if not allowed:
            st.error(f"Hourly app quota reached or unavailable ({RUNS_PER_HOUR} comparisons per rolling hour). Run blocked for safety.")
            go = False

    if go:
        # Avoid displaying a stale previous comparison if this run fails.
        st.session_state.pop("last_run", None)
        keys = [t.key for t in TECHNIQUES if t.name in selected]
        evaluate = evaluator()
        try:
            with st.status("Step 1: creating one shared task specification...", expanded=False) as status:
                # A single shared specification and test suite keeps the two coding models comparable.
                spec_debug = {}
                if source == "One-line request":
                    spec, spec_source, spec_debug = generate_shared_spec(
                        request,
                        {"Groq": llms["Groq"], "Ollama": llms["Ollama"]},
                    )
                    if spec_source != "Groq":
                        status.update(
                            label="Groq spec generation failed; using the validated Ollama specification for both models...",
                            state="running",
                        )
                else:
                    spec = spec_from_preset(preset)
                    spec_source = "Built-in preset"
                status.update(
                    label=f"Shared specification ready: {spec.signature} · {len(spec.tests)} tests · {spec_source}",
                    state="complete",
                )
            if source == "One-line request" and spec_source == "Ollama":
                st.warning("Groq could not generate a valid specification. The validated Ollama specification will be used for both models to keep the comparison fair.")
                with st.expander("Debug details"):
                    for provider_name, entries in spec_debug.items():
                        st.markdown(f"**{provider_name}**")
                        if not entries:
                            st.write("No attempt diagnostics were returned.")
                        for item in entries:
                            st.write(
                                f"Attempt {item.get('attempt', '?')} · finish_reason: {item.get('finish_reason') or 'unknown'} · "
                                f"token usage: {item.get('token_usage', {})} · error: {item.get('error_type') or 'none'}"
                            )
                            st.code(redact_error(item.get("raw_reply", "") or "(empty response)")[:300], language="text")
            progress = st.progress(0.0, text="Running every selected technique on Groq and Ollama...")
            records = run_all(
                spec,
                keys,
                llms,
                evaluate,
                trials=trials,
                workers=4,
                on_progress=lambda done, total, rec: progress.progress(
                    done / total,
                    text=f"{done}/{total}: {rec['provider']} · {rec['technique_name']} · trial {rec['trial']}",
                ),
            )
            progress.empty()
            rows = summarize(records, WEIGHT_PRESETS[priority])
            picked = pick_best(rows, records)
            score_by_key = {row["comparison_key"]: row["score"] for row in rows}
            for rec in records:
                rec.update({
                    "model": rec.get("model") or model_names.get(rec["provider"], ""),
                    "score": score_by_key.get(rec["comparison_key"]),
                })
                if rec.get("error_message"):
                    rec["error_message"] = redact_error(rec["error_message"])
                save_experiment(dict(rec))
            st.session_state["last_run"] = {
                "spec": spec, "records": records, "rows": rows, "picked": picked, "priority": priority,
                "exec_mode": exec_mode, "spec_source": spec_source,
            }
        except Exception as exc:
            if isinstance(exc, SpecGenerationError):
                st.error("Task specification generation failed on both providers. Review Debug details.")
                diagnostics = getattr(exc, "diagnostics", {})
                with st.expander("Debug details"):
                    if isinstance(diagnostics, dict):
                        for provider_name in ("Groq", "Ollama"):
                            st.markdown(f"**{provider_name}**")
                            entries = diagnostics.get(provider_name, [])
                            if not entries:
                                st.write("No attempt diagnostics were returned.")
                            for item in entries:
                                st.write(
                                    f"Attempt {item.get('attempt', '?')} · finish_reason: {item.get('finish_reason') or 'unknown'} · "
                                    f"token usage: {item.get('token_usage', {})} · error: {item.get('error_type') or 'none'}"
                                )
                                st.code(redact_error(item.get("raw_reply", "") or "(empty response)")[:300], language="text")
                    else:
                        st.write("No structured provider diagnostics were returned.")
            else:
                st.error("Comparison failed. Check provider configuration and try again.")

    run = st.session_state.get("last_run")
    if run:
        spec, records, rows, picked = run["spec"], run["records"], run["rows"], run["picked"]
        st.subheader("1. Shared task specification")
        c1, c2 = st.columns([2, 1])
        c1.markdown(f"**{spec.name}**: {spec.description}")
        c1.caption(f"Specification source: {run.get('spec_source', 'Groq')}")
        c1.code(spec.signature, language="python")
        c2.write("Visible examples")
        c2.code("\n".join(
            f"{spec.function_name}({', '.join(json.dumps(a) for a in e['args'])}) -> {json.dumps(e['expected'])}"
            for e in spec.examples
        ))
        suspects = records[0]["total_tests"] - records[0]["adj_total"]
        if suspects:
            st.warning(f"{suspects} generated test(s) were failed by every variant and treated as suspect; excluded from adjusted accuracy.")

        st.subheader("2. Same prompts sent to both models")
        st.caption("Each selected technique runs on both Groq and Ollama with the same specification, examples and hidden test cases.")
        for t in TECHNIQUES:
            if any(r["technique_key"] == t.key for r in records):
                with st.expander(f"{t.name}: {t.description}"):
                    st.code(
                        build_prompt(t.key, spec.name, spec.description, spec.function_name, spec.signature,
                                     examples=spec.examples, request=spec.request),
                        language="text",
                    )

        st.subheader("3. Groq vs Ollama: all results")
        table = pd.DataFrame([{
            "Rank": row["rank"],
            "Provider": row["provider"],
            "Technique": row["technique_name"],
            "Trials": row["trials"],
            "Usable trials": row.get("valid_trials", row["trials"]),
            "Accuracy %": round(100 * row["accuracy"], 1),
            "Solved %": round(100 * row["solved_rate"], 1),
            "Generation time (s)": None if row["gen_latency_s"] is None else round(row["gen_latency_s"], 2),
            "Tokens": None if row["tokens"] is None else round(row["tokens"]),
            "Execution time (ms)": None if row["exec_ms"] is None else round(row["exec_ms"], 4),
            "Score": row["score"],
        } for row in rows])
        table["Provider / Technique"] = table["Provider"] + " · " + table["Technique"]
        st.dataframe(table, width="stretch", hide_index=True)
        ch1, ch2, ch3 = st.columns(3)
        ch1.caption("Accuracy %")
        ch1.bar_chart(table.set_index("Provider / Technique")["Accuracy %"])
        ch2.caption("Generation time (s)")
        ch2.bar_chart(table.set_index("Provider / Technique")["Generation time (s)"])
        ch3.caption("Tokens used")
        ch3.bar_chart(table.set_index("Provider / Technique")["Tokens"])

        for rec in records:
            label = f"{rec['provider']} · {rec['technique_name']} (trial {rec['trial']}): {rec['status']} {rec['passed_tests']}/{rec['total_tests']}"
            with st.expander(label):
                if rec["error_message"]:
                    st.warning(rec["error_message"])
                st.caption(f"Model: {rec.get('model') or model_names.get(rec['provider'], 'unknown')} · Generation: {rec['latency_seconds']} s")
                if rec["generated_code"]:
                    st.code(rec["generated_code"], language="python")
                if rec["test_results"]:
                    st.dataframe(pd.DataFrame(rec["test_results"]), width="stretch", hide_index=True)

        st.subheader("4. 🏆 Best overall response")
        if not picked:
            st.error("Neither model produced a usable response. Review the API errors above.")
        else:
            top, best = picked
            st.success(
                f"**{top['provider']} · {top['technique_name']}** ranked first ({run['priority']}): "
                f"accuracy {100 * top['accuracy']:.1f}%, composite score {top['score']}/100."
            )
            st.write("Best prompt")
            st.code(best["prompt"], language="text")
            st.write("Best generated code")
            st.code(best["generated_code"], language="python")
            custom = st.text_input("Try your own input (JSON list of arguments)", placeholder="[13]")
            extra = None
            if custom.strip():
                try:
                    extra = json.loads(custom)
                    if not isinstance(extra, list):
                        raise ValueError("Use a JSON list, e.g. [13] or [[1, 2, 3], 2]")
                except Exception as exc:
                    st.error(f"Invalid input: {exc}")
                    extra = None
            outputs = show_outputs(best["generated_code"], spec, evaluator(), extra_args=extra)
            st.write("AI-estimated output" if run["exec_mode"] == "ai" else "Observed output")
            if run["exec_mode"] == "ai":
                st.caption("These outputs are Groq estimates, not results from executing Python.")
            st.dataframe(pd.DataFrame(outputs), width="stretch", hide_index=True)
            st.download_button(
                "Download this comparison as JSON",
                json.dumps({"spec": spec.__dict__, "summary": rows, "records": records}, indent=2, default=str),
                "promptlab_comparison.json", "application/json",
            )

with tab_history:
    history = get_experiments()
    if not history:
        st.info("No saved experiments yet. Run the lab to populate this dashboard.")
    else:
        df = pd.DataFrame(history)
        df["token_total"] = df["prompt_tokens"].fillna(0) + df["completion_tokens"].fillna(0)
        real = df[df["status"].isin(["PASSED", "FAILED"])]
        a, b, c = st.columns(3)
        a.metric("Saved model runs", len(df))
        b.metric("Actually executed runs", len(real))
        c.metric("Distinct requests", df["user_request"].nunique() if "user_request" in df else 0)
        if not real.empty:
            st.subheader("Results by model and technique")
            summary = real.groupby(["provider", "technique_name"], as_index=False).agg(
                Solved_Rate=("task_passed", "mean"),
                Avg_Gen_Time_s=("latency_seconds", "mean"),
                Avg_Tokens=("token_total", "mean"),
                Avg_Run_ms=("exec_ms", "mean"),
                Runs=("id", "count"),
            )
            summary["Solved_Rate"] = (summary["Solved_Rate"] * 100).round(1)
            summary["Model / Technique"] = summary["provider"] + " · " + summary["technique_name"]
            st.bar_chart(summary.set_index("Model / Technique")["Solved_Rate"])
            st.dataframe(summary, width="stretch", hide_index=True)
        cols = [x for x in [
            "id", "created_at", "user_request", "task_name", "provider", "technique_name", "trial", "model", "status",
            "passed_tests", "total_tests", "latency_seconds", "token_total", "exec_ms", "score",
        ] if x in df]
        st.dataframe(df[cols], width="stretch", hide_index=True)
        st.download_button(
            "Download history as CSV",
            safe_csv(df.drop(columns=["test_results"], errors="ignore")),
            "promptlab_experiments.csv", "text/csv",
        )
        with st.expander("View saved prompt or code"):
            record_id = st.number_input("Experiment ID", min_value=1, step=1)
            match = [r for r in history if r["id"] == record_id]
            if match:
                st.code(match[0]["prompt"], language="text")
                st.code(match[0]["generated_code"], language="python")
        if st.button("Delete all experiment history"):
            delete_all_experiments()
            st.rerun()

with tab_method:
    st.markdown("""
### Pipeline
1. **Task specification.** For a one-line request, Groq creates one shared function specification, examples and hidden tests so both coding models face the same benchmark.
2. **Dual generation.** Every selected prompt-engineering technique is sent to both Groq and Ollama automatically. No model selector is shown.
3. **Evaluation.** AI-estimate mode predicts outcomes using Groq without executing code. Actual execution is only available through an administrator-enabled Docker sandbox; host-local Python execution is disabled in the web UI.
4. **Comparison.** PromptLab compares accuracy, solved rate, generation latency, token usage and (where measured) execution time across provider × technique pairs.
5. **Ranking.** Score = 100 x (wA*accuracy + wL*speed + wT*token_efficiency + wE*run_efficiency). Default weights are 0.70 / 0.10 / 0.10 / 0.10.
6. **Output.** All model/technique outputs remain visible. The highest-ranked pair is shown with its prompt, code and example/custom outputs.

### Validity notes
- Both models receive the same prompt technique and task specification; this controls task difficulty for a fairer comparison.
- Tests generated by an LLM may have wrong expected values. A test that every model/technique fails is flagged as suspect and excluded from adjusted accuracy.
- AI-estimate mode reports predictions, not execution results. For a research paper, prioritize real Docker execution and validate generated expected values.
- Use several tasks, repeated trials (with temperature above 0) and multiple task families before drawing conclusions.
- Token counts are estimated by characters/4 when the provider does not report them.
""")
