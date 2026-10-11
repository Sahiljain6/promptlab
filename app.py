from __future__ import annotations

import os
import json
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from promptlab.prompts import TECHNIQUES, build_prompt, clean_generated_code
from promptlab.provider import generate_code
from promptlab.sandbox import evaluate_python_code
from promptlab.storage import get_experiments, save_experiment, delete_all_experiments
from promptlab.tasks import PRESET_TASKS

load_dotenv()
st.set_page_config(page_title="PromptLab", page_icon="🧪", layout="wide")
st.title("🧪 PromptLab")
st.caption("A Comparative Study of Prompt Engineering Techniques for Improving Code Generation Accuracy in LLMs")
st.markdown("Compare prompt strategies using model-generated Python code and automated ground-truth tests. Provider credentials are loaded from server-side secrets and are not displayed in the interface.")

def secret_or_env(name: str, default: str = "") -> str:
    """Read credentials from Streamlit Secrets first, then local environment variables."""
    try:
        value = st.secrets.get(name, os.getenv(name, default))
    except Exception:
        value = os.getenv(name, default)
    return str(value or "")


with st.sidebar:
    st.header("Model configuration")
    provider = st.selectbox("Provider", ["Groq", "OpenAI", "Custom OpenAI-compatible"])
    if provider == "Groq":
        api_key = secret_or_env("GROQ_API_KEY")
        model_default, base_url = "openai/gpt-oss-20b", "https://api.groq.com/openai/v1"
        secret_name = "GROQ_API_KEY"
    elif provider == "OpenAI":
        api_key = secret_or_env("OPENAI_API_KEY")
        model_default, base_url = "gpt-4o-mini", ""
        secret_name = "OPENAI_API_KEY"
    else:
        api_key = secret_or_env("PROMPTLAB_API_KEY")
        model_default = secret_or_env("PROMPTLAB_MODEL")
        base_url = st.text_input("API base URL", value=secret_or_env("PROMPTLAB_BASE_URL"))
        secret_name = "PROMPTLAB_API_KEY"
    model = st.text_input("Model ID", value=model_default)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.0, 0.1)
    if not api_key:
        st.warning(f"Provider key is not configured. Add {secret_name} under Streamlit app Settings → Secrets, or set it in your local .env file.")
    st.divider()
    judge0_api_key = secret_or_env("JUDGE0_API_KEY")
    if judge0_api_key:
        st.caption("Cloud sandbox credentials: configured. The key is stored server-side and is not shown.")
    else:
        st.caption("Cloud sandbox credentials: not configured. Add JUDGE0_API_KEY under Streamlit app Settings → Secrets. Local runs can use Docker Desktop.")

tab_run, tab_history, tab_method = st.tabs(["Run experiment", "History & analysis", "Research protocol"])

with tab_run:
    task_choice = st.selectbox("Benchmark task", list(PRESET_TASKS) + ["Custom task"])
    test_error = ""
    if task_choice == "Custom task":
        task_name = st.text_input("Task name", "Custom function task")
        task_description = st.text_area("Task specification", "Describe expected behavior and edge cases.")
        function_name = st.text_input("Required function name", "solve")
        signature = st.text_input("Required function signature", "def solve(value)")
        raw_tests = st.text_area("Test cases JSON", '[{"args": [2], "expected": 4}]')
        try:
            tests = json.loads(raw_tests)
            if not isinstance(tests, list):
                raise ValueError("Test cases must be a JSON list.")
        except Exception as exc:
            tests, test_error = [], str(exc)
        if test_error:
            st.error("Invalid test JSON: " + test_error)
    else:
        task = PRESET_TASKS[task_choice]
        task_name, task_description = task["name"], task["description"]
        function_name, signature, tests = task["function_name"], task["signature"], task["tests"]
        st.info(task_description)
        st.write("Required function: " + signature)
        st.write("Ground-truth test cases: " + str(len(tests)))
    selected = st.multiselect("Prompt techniques to compare", [t.name for t in TECHNIQUES], default=[t.name for t in TECHNIQUES])
    run = st.button("Run experiment", type="primary", disabled=(not api_key or not model or not selected or not tests or bool(test_error)))
    if run:
        progress = st.progress(0)
        all_rows = []
        chosen = [t for t in TECHNIQUES if t.name in selected]
        for index, technique in enumerate(chosen):
            st.subheader(technique.name)
            prompt = build_prompt(technique.key, task_name, task_description, function_name, signature)
            try:
                generated = generate_code(provider=provider, api_key=api_key, model=model, prompt=prompt,
                                          temperature=temperature, custom_base_url=base_url)
                code = clean_generated_code(generated.text)
                evaluation = evaluate_python_code(code, function_name, tests, judge0_api_key=judge0_api_key)
                record = {
                    "task_name": task_name, "function_name": function_name, "provider": provider,
                    "model": generated.model, "technique_key": technique.key, "technique_name": technique.name,
                    "prompt": prompt, "generated_code": code, "status": evaluation["status"],
                    "task_passed": int(evaluation["task_passed"]), "passed_tests": evaluation["passed_tests"],
                    "total_tests": evaluation["total_tests"], "latency_seconds": generated.latency_seconds,
                    "prompt_tokens": generated.prompt_tokens, "completion_tokens": generated.completion_tokens,
                    "test_results": evaluation["results"], "error_message": evaluation["error"],
                }
                record["id"] = save_experiment(record)
                all_rows.append(record)
                c1, c2, c3 = st.columns(3)
                c1.metric("Test result", evaluation["status"])
                c2.metric("Passed tests", f'{evaluation["passed_tests"]}/{evaluation["total_tests"]}')
                c3.metric("Model latency", f'{generated.latency_seconds:.2f}s')
                st.code(code, language="python")
                if evaluation["error"]:
                    st.warning(evaluation["error"])
                if evaluation["results"]:
                    st.dataframe(pd.DataFrame(evaluation["results"]), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Generation failed: {type(exc).__name__}: {exc}")
                try:
                    save_experiment({"task_name": task_name, "function_name": function_name, "provider": provider,
                        "model": model, "technique_key": technique.key, "technique_name": technique.name,
                        "prompt": prompt, "generated_code": "", "status": "API ERROR", "task_passed": 0,
                        "passed_tests": 0, "total_tests": len(tests), "error_message": str(exc), "test_results": []})
                except Exception:
                    pass
            progress.progress((index + 1) / len(chosen))
        if all_rows:
            st.success(f"Saved {len(all_rows)} experiment result(s).")
            st.dataframe(pd.DataFrame([{"Technique": x["technique_name"], "Status": x["status"],
                "Passed": f'{x["passed_tests"]}/{x["total_tests"]}', "Latency (s)": x["latency_seconds"],
                "Model": x["model"]} for x in all_rows]), use_container_width=True, hide_index=True)

with tab_history:
    history = get_experiments()
    if not history:
        st.info("No saved experiments yet. Run an experiment to populate the dashboard.")
    else:
        df = pd.DataFrame(history)
        a, b, c = st.columns(3)
        tested = df[df["status"].isin(["PASSED", "FAILED"])]
        a.metric("Saved runs", len(df))
        b.metric("Fully passed", int((df["status"] == "PASSED").sum()))
        c.metric("Tested runs", len(tested))
        if not tested.empty:
            summary = tested.groupby("technique_name", as_index=False).agg(
                Task_Success_Rate=("task_passed", "mean"), Average_Latency=("latency_seconds", "mean"), Runs=("id", "count"))
            summary["Task_Success_Rate"] *= 100
            st.subheader("Task success rate by technique (%)")
            st.bar_chart(summary.set_index("technique_name")["Task_Success_Rate"])
            st.dataframe(summary, use_container_width=True, hide_index=True)
        st.subheader("Experiment records")
        columns = [x for x in ["id", "created_at", "task_name", "technique_name", "model", "status", "passed_tests",
                               "total_tests", "latency_seconds", "prompt_tokens", "completion_tokens"] if x in df]
        st.dataframe(df[columns], use_container_width=True, hide_index=True)
        st.download_button("Download history as CSV", df.drop(columns=["test_results"], errors="ignore").to_csv(index=False),
                           "promptlab_experiments.csv", "text/csv")
        with st.expander("View saved code or prompt"):
            record_id = st.number_input("Experiment ID", min_value=1, step=1)
            matching = [r for r in history if r["id"] == record_id]
            if matching:
                st.write("Prompt")
                st.code(matching[0]["prompt"], language="text")
                st.write("Generated code")
                st.code(matching[0]["generated_code"], language="python")
        if st.button("Delete all experiment history"):
            delete_all_experiments()
            st.rerun()

with tab_method:
    st.subheader("How to run a fair comparison")
    st.markdown("""
1. Use the same model ID, task specification, test cases, and temperature for each technique.
2. Run all techniques against the same task and repeat trials to account for model variability.
3. Ground-truth tests are the evaluation oracle and are not included in the prompt.
4. Report task success rate, test pass rate, latency, and token counts when available.
5. Record model/version, date, task IDs, prompt templates, and provider changes.
6. Avoid broad claims from a small number of tasks; expand the benchmark and repeat trials.

**Task success rate:** percentage of generated solutions passing every test. **Test pass rate:** passed cases divided by executed cases. Latency measures API response time and excludes test execution.

**Limitations:** Preset tasks are a starter suite, not a standardized benchmark. API errors and runs not tested because Docker is unavailable are not verified code failures.
""")
