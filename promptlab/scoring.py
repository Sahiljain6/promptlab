from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

# (accuracy, generation latency, token usage, execution time)
WEIGHT_PRESETS: dict[str, tuple[float, float, float, float]] = {
    "Accuracy first": (0.70, 0.10, 0.10, 0.10),
    "Balanced": (0.50, 0.20, 0.15, 0.15),
    "Speed & cost first": (0.30, 0.30, 0.25, 0.15),
}
EXECUTED = {"PASSED", "FAILED"}
LATENCY_EPS_S = 0.05     # floors so tiny absolute differences do not dominate the ratio
EXEC_EPS_MS = 0.05


def flag_suspect_tests(records: list[dict[str, Any]], min_runs: int = 3) -> set[int]:
    """Indexes of tests that EVERY candidate failed. With several independent candidates this usually means the
    LLM-written expected value is wrong, so such tests are excluded from the adjusted score (and reported)."""
    runs = [r for r in records if r.get("status") in EXECUTED and len(r.get("test_results") or []) == r.get("total_tests")]
    if len(runs) < min_runs:
        return set()
    total = runs[0]["total_tests"]
    suspects = {i for i in range(total) if not any(r["test_results"][i].get("passed") for r in runs)}
    return set() if len(suspects) == total else suspects


def annotate(records: list[dict[str, Any]], suspects: set[int]) -> None:
    for r in records:
        total = int(r.get("total_tests") or 0)
        results = r.get("test_results") or []
        adj_total = total - len(suspects)
        if results and len(results) == total:
            adj_passed = sum(1 for i, item in enumerate(results) if i not in suspects and item.get("passed"))
        else:
            adj_passed = 0
        r["adj_passed"], r["adj_total"] = adj_passed, adj_total
        r["adj_rate"] = adj_passed / adj_total if adj_total else 0.0
        r["solved"] = bool(adj_total and adj_passed == adj_total)


def _norm_low(value: float | None, best: float | None, eps: float) -> float:
    if value is None or best is None:
        return 0.0
    return (best + eps) / (value + eps)


def summarize(records: list[dict[str, Any]], weights: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    """One row per provider × technique, ranked by composite score (0-100)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    providers = {r.get("provider", "Model") for r in records}
    for r in records:
        provider = r.get("provider", "Model")
        groups[(provider, r["technique_key"])].append(r)
    rows = []
    for (provider, key), items in groups.items():
        ok = [r for r in items if r.get("status") not in {"API ERROR", "NOT TESTED"}]
        times = [r["exec_ms"] for r in ok if r.get("exec_ms") is not None]
        display = f"{provider} · {items[0]['technique_name']}" if len(providers) > 1 else items[0]["technique_name"]
        rows.append({
            "comparison_key": f"{provider}::{key}",
            "provider": provider,
            "technique_key": key,
            "technique": display,
            "technique_name": items[0]["technique_name"],
            "trials": len(items),
            "valid_trials": len(ok),
            # API errors and NOT TESTED trials are missing observations, not incorrect solutions.
            "accuracy": mean(r["adj_rate"] for r in ok) if ok else 0.0,
            "solved_rate": mean(1.0 if r["solved"] else 0.0 for r in ok) if ok else 0.0,
            "gen_latency_s": mean(r["latency_seconds"] for r in ok if r.get("latency_seconds") is not None) if any(r.get("latency_seconds") is not None for r in ok) else None,
            "tokens": mean((r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in ok) if ok else None,
            "exec_ms": mean(times) if times else None,
        })
    best_lat = min((r["gen_latency_s"] for r in rows if r["gen_latency_s"] is not None), default=None)
    best_tok = min((r["tokens"] for r in rows if r["tokens"]), default=None)
    best_exec = min((r["exec_ms"] for r in rows if r["exec_ms"] is not None), default=None)
    w_acc, w_lat, w_tok, w_exec = weights
    for row in rows:
        lat = _norm_low(row["gen_latency_s"], best_lat, LATENCY_EPS_S)
        tok = _norm_low(row["tokens"], best_tok, 0.0) if row["tokens"] else 0.0
        exe = _norm_low(row["exec_ms"], best_exec, EXEC_EPS_MS)
        if row["exec_ms"] is None and best_exec is None:
            exe = 1.0      # nobody reported execution time (AI-estimate mode): neutral
        row["score"] = (
            round(100 * (w_acc * row["accuracy"] + w_lat * lat + w_tok * tok + w_exec * exe), 2)
            if row["valid_trials"] else 0.0
        )
    rows.sort(key=lambda r: (-r["score"], r["tokens"] or 1e9))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def pick_best(rows: list[dict[str, Any]], records: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Best provider-and-technique pair and its best individual trial."""
    if not rows:
        return None
    top = rows[0]
    trials = [
        r for r in records
        if r["technique_key"] == top["technique_key"]
        and r.get("provider", "Model") == top.get("provider", "Model")
        and r.get("status") not in {"API ERROR", "NOT TESTED"}
    ]
    if not trials:
        return None
    best = max(trials, key=lambda r: (
        r["adj_rate"],
        -((r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0))
    ))
    return top, best
