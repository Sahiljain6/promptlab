from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from .prompts import (TECHNIQUE_BY_KEY, TECHNIQUES, build_prompt, build_repair_prompt, clean_generated_code,
                      max_tokens_for, system_for)
from .provider import generate_code
from .scoring import annotate, flag_suspect_tests
from .tasks import TaskSpec

LLM = Callable[..., Any]            # (prompt, system=None, max_tokens=...) -> object with text/latency/tokens
Evaluator = Callable[[str, str, list], dict]
REPAIRABLE = {"FAILED", "AI FAIL", "SYNTAX ERROR", "EXECUTION ERROR", "TIMEOUT", "BLOCKED", "RUNNER ERROR"}
MAX_REPAIR_ROUNDS = 2


def make_llm(provider: str, api_key: str, model: str, temperature: float = 0.0, base_url: str = "") -> LLM:
    def call(prompt: str, system: str | None = None, max_tokens: int = 1500,
             response_format: dict[str, Any] | None = None,
             reasoning_effort: str | None = None):
        return generate_code(
            provider=provider,
            api_key=api_key,
            model=model,
            prompt=prompt,
            temperature=temperature,
            custom_base_url=base_url,
            system=system,
            max_tokens=max_tokens,
            response_format=response_format,
            reasoning_effort=reasoning_effort,
        )
    call.provider_name = "Groq" if provider == "Groq" else (
        "Ollama" if "ollama.com" in base_url else provider
    )
    return call


def _tokens(gen: Any, prompt: str) -> tuple[int, int]:
    """API-reported token counts, or a rough chars/4 estimate when the provider omits usage."""
    p = getattr(gen, "prompt_tokens", None)
    c = getattr(gen, "completion_tokens", None)
    return (p if p is not None else max(1, len(prompt) // 4)), (c if c is not None else max(1, len(gen.text) // 4))


def _feedback(evaluation: dict, tests: list[dict]) -> str:
    if evaluation.get("error") and not evaluation.get("results"):
        return str(evaluation["error"])
    lines = []
    for item in evaluation.get("results", []):
        if not item.get("passed"):
            case = tests[item["case"] - 1]
            args = ", ".join(json.dumps(a, ensure_ascii=False) for a in case.get("args", []))
            got = item.get("error") if item.get("actual") is None else item.get("actual")
            lines.append(f"input ({args}) expected {json.dumps(case.get('expected'))} but got {got}")
    return "\n".join(lines[:6]) or "The code did not pass the examples."


def run_technique(technique_key: str, spec: TaskSpec, llm: LLM, evaluate: Evaluator, trial: int = 1) -> dict[str, Any]:
    technique = TECHNIQUE_BY_KEY[technique_key]
    prompt = build_prompt(technique_key, spec.name, spec.description, spec.function_name, spec.signature,
                          examples=spec.examples, request=spec.request)
    record: dict[str, Any] = {
        "technique_key": technique.key, "technique_name": technique.name, "trial": trial, "prompt": prompt,
        "generated_code": "", "status": "API ERROR", "task_passed": 0, "passed_tests": 0,
        "total_tests": len(spec.tests), "latency_seconds": None, "prompt_tokens": None, "completion_tokens": None,
        "exec_ms": None, "test_results": [], "error_message": None, "rounds": 1, "model": None,
    }
    try:
        system, max_tokens = system_for(technique_key), max_tokens_for(technique_key)
        gen = llm(prompt, system=system, max_tokens=max_tokens)
        generated_text = getattr(gen, "text", None)
        if not isinstance(generated_text, str) or not generated_text.strip():
            raise RuntimeError("Provider returned empty generation content.")
        latency, (p_tok, c_tok) = gen.latency_seconds, _tokens(gen, prompt)
        record["model"] = getattr(gen, "model", None)
        code = clean_generated_code(gen.text, spec.function_name)
        if technique.multi_call:
            for _ in range(MAX_REPAIR_ROUNDS):
                check = evaluate(code, spec.function_name, spec.examples)
                if check["status"] not in REPAIRABLE:
                    break
                repair = build_repair_prompt(prompt, code, _feedback(check, spec.examples))
                gen = llm(repair, system=system, max_tokens=max_tokens)
                generated_text = getattr(gen, "text", None)
                if not isinstance(generated_text, str) or not generated_text.strip():
                    raise RuntimeError("Provider returned empty generation content during repair.")
                latency += gen.latency_seconds
                extra_p, extra_c = _tokens(gen, repair)
                p_tok, c_tok = p_tok + extra_p, c_tok + extra_c
                code = clean_generated_code(gen.text, spec.function_name)
                record["rounds"] += 1
        evaluation = evaluate(code, spec.function_name, spec.tests)
        record.update({
            "generated_code": code, "status": evaluation["status"], "task_passed": int(evaluation["task_passed"]),
            "passed_tests": evaluation["passed_tests"], "latency_seconds": round(latency, 3),
            "prompt_tokens": p_tok, "completion_tokens": c_tok, "exec_ms": evaluation.get("exec_ms"),
            "test_results": evaluation["results"], "error_message": evaluation["error"],
            "exec_mode": evaluation.get("mode"),
        })
    except Exception as exc:
        record["error_message"] = f"{type(exc).__name__}: {exc}"
    return record


def run_all(spec: TaskSpec, technique_keys: list[str], llm: LLM | dict[str, LLM], evaluate: Evaluator, trials: int = 1,
            workers: int = 4, on_progress: Callable[[int, int, dict], None] | None = None,
            fallback_llm: LLM | None = None,
            fallback_provider_name: str = "Gemini (fallback)") -> list[dict[str, Any]]:
    """Run every selected technique against one or more models using the same task and tests.

    A single LLM preserves the original API; a mapping creates provider × technique pairs.
    An optional fallback client is contacted only when every primary provider reports an API error
    for the same technique and trial. It is not added to normal comparison runs.
    """
    order = {t.key: i for i, t in enumerate(TECHNIQUES)}
    llms = llm if isinstance(llm, dict) else {"Model": llm}
    jobs = [(provider, client, key, trial)
            for provider, client in llms.items()
            for key in technique_keys
            for trial in range(1, trials + 1)]
    possible_fallbacks = len(technique_keys) * trials if fallback_llm is not None and len(llms) >= 2 else 0
    progress_total = len(jobs) + possible_fallbacks
    progress_done = 0
    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(run_technique, key, spec, client, evaluate, trial): provider
            for provider, client, key, trial in jobs
        }
        for done, future in enumerate(as_completed(futures), 1):
            record = future.result()
            record["provider"] = futures[future]
            record["comparison_key"] = f"{record['provider']}::{record['technique_key']}"
            records.append(record)
            progress_done = done
            if on_progress:
                on_progress(done, progress_total, record)

    # Keep the backup idle unless both primary providers fail to return usable API responses
    # for the same prompt technique and trial. The one successful primary result is not replaced.
    if fallback_llm is not None and len(llms) >= 2:
        primary_records = list(records)
        for key in technique_keys:
            for trial in range(1, trials + 1):
                pair = [
                    record for record in primary_records
                    if record["technique_key"] == key and record["trial"] == trial
                ]
                if len(pair) != len(llms) or not all(record["status"] == "API ERROR" for record in pair):
                    continue
                fallback_record = run_technique(key, spec, fallback_llm, evaluate, trial)
                fallback_record["provider"] = fallback_provider_name
                fallback_record["comparison_key"] = f"{fallback_provider_name}::{key}"
                records.append(fallback_record)
                progress_done += 1
                if on_progress:
                    on_progress(progress_done, progress_total, fallback_record)

    if on_progress and records and progress_done < progress_total:
        on_progress(progress_total, progress_total, records[-1])

    provider_order = {name: index for index, name in enumerate(llms)}
    if fallback_llm is not None:
        provider_order[fallback_provider_name] = len(provider_order)
    records.sort(key=lambda r: (provider_order.get(r["provider"], 99), order[r["technique_key"]], r["trial"]))
    annotate(records, flag_suspect_tests(records))
    run_id = uuid.uuid4().hex[:10]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for r in records:
        r.update({"run_id": run_id, "created_at": stamp, "task_name": spec.name, "function_name": spec.function_name,
                  "user_request": spec.request})
    return records


def show_outputs(code: str, spec: TaskSpec, evaluate: Evaluator, extra_args: list | None = None) -> list[dict[str, Any]]:
    """Run the winning code on the visible examples (and an optional custom input) and report the real outputs."""
    cases = [{"args": ex["args"], "expected": None} for ex in spec.examples]
    if extra_args is not None:
        cases.append({"args": extra_args, "expected": None})
    result = evaluate(code, spec.function_name, cases)
    rows = []
    for case, item in zip(cases, result.get("results", [])):
        args = ", ".join(json.dumps(a, ensure_ascii=False) for a in case["args"])
        rows.append({"call": f"{spec.function_name}({args})", "output": item.get("actual") if item.get("actual") is not None else item.get("error"),
                     "time_ms": item.get("ms")})
    if not rows and result.get("error"):
        rows.append({"call": spec.function_name + "(...)", "output": result["error"], "time_ms": None})
    return rows
