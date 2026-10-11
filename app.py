from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from promptlab.pipeline import make_llm, run_all, show_outputs
from promptlab.prompts import TECHNIQUES, build_prompt
from promptlab.sandbox import docker_available, evaluate_python_code
from promptlab.scoring import WEIGHT_PRESETS, pick_best, summarize
from promptlab.storage import delete_all_experiments, get_experiments, save_experiment
from promptlab.tasks import PRESET_TASKS, expand_request, spec_from_preset

load_dotenv()
st.set_page_config(page_title="PromptLab", page_icon="🧪", layout="wide")
st.title("🧪 PromptLab")
st.caption("An Automated Benchmarking Framework for Prompt Engineering Techniques in LLM Code Generation: "
           "accuracy, latency, token cost and execution efficiency")


def secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, os.getenv(name, default))
    except Exception:
        value = os.getenv(name, default)
    return str(value or "")


EXEC_MODES = {"Auto (Docker if available, else local Python)": "auto", "Local Python (subprocess)": "local",
              "Docker sandbox": "docker", "AI estimate via Groq (does not execute)": "ai"}

with st.sidebar:
    st.header("Model")
    provider = st.selectbox("Provider", ["Groq", "OpenAI", "Custom OpenAI-compatible"])
    if provider == "Groq":
        api_key, model_default, base_url, secret_name = secret_or_env("GROQ_API_KEY"), "openai/gpt-oss-20b", "", "GROQ_API_KEY"
    elif provider == "OpenAI":
        api_key, model_default, base_url, secret_name = secret_or_env("OPENAI_API_KEY"), "gpt-4o-mini", "", "OPENAI_API_KEY"
    else:
        api_key, model_default, secret_name = secret_or_env("PROMPTLAB_API_KEY"), secret_or_env("PROMPTLAB_MODEL"), "PROMPTLAB_API_KEY"
        base_url = st.text_input("API base URL", value=secret_or_env("PROMPTLAB_BASE_URL"))
    model = st.text_input("Model ID", value=model_default)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.0, 0.1)
    if not api_key:
        st.warning(f"Add {secret_name} to your .env file or Streamlit Secrets.")
    st.header("Experiment")
    exec_label = st.selectbox("Test executor", list(EXEC_MODES), help="Local/Docker run the code for real. AI estimate only predicts outcomes.")
    exec_mode = EXEC_MODES[exec_label]
    trials = st.slider("Trials per technique", 1, 5, 1, help="Use >1 with temperature > 0 to average out randomness.")
    priority = st.selectbox("Best-prompt priority", list(WEIGHT_PRESETS), help="Weights: accuracy / generation time / tokens / execution time")
    st.caption("Docker detected." if docker_available() else "Docker not detected; local Python executor will be used.")


def evaluator():
    groq_key, groq_model = secret_or_env("GROQ_API_KEY"), secret_or_env("GROQ_TEST_MODEL", "openai/gpt-oss-20b")
    return lambda code, fn, tests: evaluate_python_code(code, fn, tests, mode=exec_mode, groq_api_key=groq_key, groq_model=groq_model)


tab_run, tab_history, tab_method = st.tabs(["⚡ Prompt Lab", "History & analysis", "Research protocol"])

with tab_run:
    source = st.radio("Task source", ["One-line request", "Preset benchmark task"], horizontal=True)
    request = ""
    if source == "One-line request":
        request = st.text_input("Describe the code you want in one line",
                                placeholder="e.g. find the second largest number in a list without sorting")
    else:
        preset = st.selectbox("Benchmark task", list(PRESET_TASKS))
    selected = st.multiselect("Prompt techniques", [t.name for t in TECHNIQUES], default=[t.name for t in TECHNIQUES])
    ready = bool(api_key and model and selected and (request.strip() or source != "One-line request"))
    go = st.button("Generate prompts, run every technique, find the best", type="primary", disabled=not ready)

    if go:
        llm, evaluate = make_llm(provider, api_key, model, temperature, base_url), evaluator()
        keys = [t.key for t in TECHNIQUES if t.name in selected]
        try:
            with st.status("Step 1: turning your request into a specification and hidden tests...", expanded=False) as status:
                spec = expand_request(request, llm) if source == "One-line request" else spec_from_preset(preset)
                status.update(label=f"Step 1 done: `{spec.signature}` with {len(spec.tests)} hidden tests", state="complete")
            progress = st.progress(0.0, text="Step 2: running techniques...")
            records = run_all(spec, keys, llm, evaluate, trials=trials,
                              on_progress=lambda done, total, rec: progress.progress(done / total, text=f"{done}/{total} finished: {rec['technique_name']}"))
            progress.empty()
            rows = summarize(records, WEIGHT_PRESETS[priority])
            picked = pick_best(rows, records)
            score_by_key = {r["technique_key"]: r["score"] for r in rows}
            for rec in records:
                rec.update({"provider": provider, "model": rec.get("model") or model, "score": score_by_key.get(rec["technique_key"])})
                save_experiment(dict(rec))
            st.session_state["last_run"] = {"spec": spec, "records": records, "rows": rows, "picked": picked, "priority": priority}
        except Exception as exc:
            st.error(f"{type(exc).__name__}: {exc}")

    run = st.session_state.get("last_run")
    if run:
        spec, records, rows, picked = run["spec"], run["records"], run["rows"], run["picked"]
        st.subheader("1. Specification generated from your line")
        c1, c2 = st.columns([2, 1])
        c1.markdown(f"**{spec.name}**: {spec.description}")
        c1.code(spec.signature, language="python")
        c2.write("Visible examples")
        c2.code("\n".join(f"{spec.function_name}({', '.join(json.dumps(a) for a in e['args'])}) -> {json.dumps(e['expected'])}" for e in spec.examples))
        suspects = records[0]["total_tests"] - records[0]["adj_total"]
        if suspects:
            st.warning(f"{suspects} generated test(s) were failed by every technique and are treated as suspect (probably wrong expected values). They are excluded from accuracy.")

        st.subheader("2. The same line as a prompt for every technique")
        for t in TECHNIQUES:
            if any(r["technique_key"] == t.key for r in records):
                with st.expander(f"{t.name}: {t.description}"):
                    st.code(build_prompt(t.key, spec.name, spec.description, spec.function_name, spec.signature,
                                         examples=spec.examples, request=spec.request), language="text")

        st.subheader("3. Accuracy and time efficiency")
        table = pd.DataFrame([{
            "Rank": r["rank"], "Technique": r["technique"], "Accuracy %": round(100 * r["accuracy"], 1),
            "Solved %": round(100 * r["solved_rate"], 1),
            "Gen time (s)": None if r["gen_latency_s"] is None else round(r["gen_latency_s"], 2),
            "Tokens": None if r["tokens"] is None else round(r["tokens"]),
            "Run time (ms)": None if r["exec_ms"] is None else round(r["exec_ms"], 4), "Score": r["score"]} for r in rows])
        st.dataframe(table, width="stretch", hide_index=True)
        a, b, c = st.columns(3)
        a.caption("Accuracy %"); a.bar_chart(table.set_index("Technique")["Accuracy %"])
        b.caption("Generation time (s)"); b.bar_chart(table.set_index("Technique")["Gen time (s)"])
        c.caption("Tokens used"); c.bar_chart(table.set_index("Technique")["Tokens"])
        for rec in records:
            label = f"{rec['technique_name']} (trial {rec['trial']}): {rec['status']} {rec['passed_tests']}/{rec['total_tests']}"
            with st.expander(label):
                if rec["error_message"]:
                    st.warning(rec["error_message"])
                if rec["generated_code"]:
                    st.code(rec["generated_code"], language="python")
                if rec["test_results"]:
                    st.dataframe(pd.DataFrame(rec["test_results"]), width="stretch", hide_index=True)

        st.subheader("4. 🏆 Best prompt and its output")
        if not picked:
            st.error("No technique produced usable code. Check the API key, model ID and errors above.")
        else:
            top, best = picked
            st.success(f"**{top['technique']}** ranked first ({run['priority']}): accuracy {100 * top['accuracy']:.0f}%, "
                       f"score {top['score']}/100, {best['rounds']} model call(s) in the best trial.")
            st.write("Best prompt")
            st.code(best["prompt"], language="text")
            st.write("Code it produced")
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
            st.write("Real output")
            st.dataframe(pd.DataFrame(outputs), width="stretch", hide_index=True)
            st.download_button("Download this run as JSON", json.dumps({"spec": spec.__dict__, "summary": rows,
                               "records": [{k: v for k, v in r.items()} for r in records]}, indent=2, default=str),
                               "promptlab_run.json", "application/json")

with tab_history:
    history = get_experiments()
    if not history:
        st.info("No saved experiments yet. Run the lab to populate this dashboard.")
    else:
        df = pd.DataFrame(history)
        df["token_total"] = df["prompt_tokens"].fillna(0) + df["completion_tokens"].fillna(0)
        real = df[df["status"].isin(["PASSED", "FAILED"])]
        a, b, c = st.columns(3)
        a.metric("Saved runs", len(df)); b.metric("Executed runs", len(real)); c.metric("Distinct requests", df["user_request"].nunique())
        if not real.empty:
            st.subheader("Technique performance across all executed runs")
            summary = real.groupby("technique_name", as_index=False).agg(
                Solved_Rate=("task_passed", "mean"), Avg_Gen_Time_s=("latency_seconds", "mean"),
                Avg_Tokens=("token_total", "mean"), Avg_Run_ms=("exec_ms", "mean"), Runs=("id", "count"))
            summary["Solved_Rate"] = (summary["Solved_Rate"] * 100).round(1)
            st.bar_chart(summary.set_index("technique_name")["Solved_Rate"])
            st.dataframe(summary, width="stretch", hide_index=True)
        cols = [x for x in ["id", "created_at", "user_request", "task_name", "technique_name", "trial", "model", "status",
                            "passed_tests", "total_tests", "latency_seconds", "token_total", "exec_ms", "score"] if x in df]
        st.dataframe(df[cols], width="stretch", hide_index=True)
        st.download_button("Download history as CSV", df.drop(columns=["test_results"], errors="ignore").to_csv(index=False),
                           "promptlab_experiments.csv", "text/csv")
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
1. **Request to specification.** One LLM call converts your line into a function name, typed signature, description, 2 visible examples and 8-10 hidden tests.
2. **Prompt generation.** The same request is turned into 10 prompt templates (zero-shot, few-shot, persona, signature+docstring, structured spec, private planning, CoT, structured CoT, decomposition, self-repair).
3. **Generation.** Every prompt is sent to the same model with the same temperature; latency and token usage are recorded (self-repair sums all of its calls).
4. **Execution.** Code is run against the hidden tests in Docker or a local subprocess with timeouts; per-call run time is measured (best of repeated calls).
5. **Scoring.** `score = 100 x (wA*accuracy + wL*speed + wT*token_efficiency + wE*run_efficiency)`; efficiency terms are best/value ratios across techniques. The default weights are 0.70 / 0.10 / 0.10 / 0.10.
6. **Result.** The top-ranked technique's prompt, code and real outputs are shown, and you can try your own input.

### Validity notes
- The zero-shot baseline sees only your raw line and the function name; richer techniques add the specification, signature or examples, so the comparison measures what each technique adds.
- Tests are LLM-generated, so a test that every technique fails is flagged as suspect and excluded from adjusted accuracy. For the paper, also report results on the preset benchmark tasks, whose tests are hand-written.
- Use several tasks, repeated trials (with temperature above 0) and more than one model before drawing conclusions.
- Token counts fall back to a chars/4 estimate if the provider omits usage.
- AI-estimate mode only predicts outcomes and must be reported as an estimate, not as execution.
""")
