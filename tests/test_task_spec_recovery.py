import json
import unittest
from types import SimpleNamespace as NS

from promptlab.pipeline import run_all
from promptlab.provider import SpecGenerationError
from promptlab.tasks import _extract_json, expand_request, generate_shared_spec


SPEC = {
    "name": "Transaction analyzer",
    "function_name": "analyze_transactions",
    "signature": "def analyze_transactions(transactions: list[dict], start_date: str, end_date: str) -> dict",
    "description": "Summarize transactions in an inclusive valid date range; return an error object for invalid dates or reversed ranges.",
    "examples": [
        {"args": [[], "2026-01-01", "2026-01-31"], "expected": {"income": 0, "expense": 0}},
        {"args": [[], "2026-03-01", "2026-02-28"], "expected": {"error": "invalid date range"}},
    ],
    "tests": [
        {"args": [[], "2026-01-02", "2026-01-31"], "expected": {"income": 0, "expense": 0}},
        {"args": [[], "2026-02-01", "2026-02-28"], "expected": {"income": 0, "expense": 0}},
        {"args": [[{"id": 1, "date": "2026-01-03", "amount": 10, "category": "food", "type": "expense", "status": "completed"}], "2026-01-01", "2026-01-31"], "expected": {"income": 0, "expense": 10}},
        {"args": [[{"id": 2, "date": "2026-01-04", "amount": 20, "category": "salary", "type": "income", "status": "completed"}], "2026-01-01", "2026-01-31"], "expected": {"income": 20, "expense": 0}},
        {"args": [[{"id": 3, "date": "2026-01-05", "amount": 20, "category": "salary", "type": "income", "status": "cancelled"}], "2026-01-01", "2026-01-31"], "expected": {"income": 0, "expense": 0}},
        {"args": [[], "bad-date", "2026-01-31"], "expected": {"error": "invalid date"}},
        {"args": [[], "2026-02-01", "2026-01-01"], "expected": {"error": "invalid date range"}},
        {"args": [[{"id": 4, "date": "2026-02-01", "amount": 5, "category": "travel", "type": "expense", "status": "completed"}], "2026-02-01", "2026-02-01"], "expected": {"income": 0, "expense": 5}},
    ],
}


def json_reply(**overrides):
    payload = dict(SPEC)
    payload.update(overrides)
    return json.dumps(payload)


class TaskSpecRecoveryTests(unittest.TestCase):
    def test_groq_400_failed_generation_json_is_recovered(self):
        calls = []

        def groq_call(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append({"max_tokens": max_tokens, "response_format": response_format, "reasoning_effort": reasoning_effort})
            raise SpecGenerationError(
                "Provider rejected the generation request.",
                provider="Groq",
                failed_generation=json_reply(),
            )

        spec = expand_request("Analyze transactions by date range and status", groq_call, provider_name="Groq")
        self.assertEqual(spec.function_name, "analyze_transactions")
        self.assertEqual(len(spec.tests), 8)
        self.assertEqual(calls[0]["response_format"], {"type": "json_object"})
        self.assertEqual(calls[0]["reasoning_effort"], "low")

    def test_empty_length_response_escalates_token_budget(self):
        calls = []

        def flaky(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append({"max_tokens": max_tokens, "response_format": response_format, "reasoning_effort": reasoning_effort})
            if len(calls) == 1:
                return NS(text="", finish_reason="length", prompt_tokens=4000, completion_tokens=0, reasoning_tokens=3000)
            return NS(text=json_reply(), finish_reason="stop", prompt_tokens=400, completion_tokens=900, reasoning_tokens=100)

        spec = expand_request("Analyze transactions by date range and status", flaky, provider_name="Groq")
        self.assertEqual(spec.function_name, "analyze_transactions")
        self.assertEqual(calls[0]["max_tokens"], 6000)
        self.assertEqual(calls[1]["max_tokens"], 8000)
        self.assertEqual(calls[0]["reasoning_effort"], "low")

    def test_truncated_final_test_is_dropped_but_five_complete_tests_survive(self):
        payload = dict(SPEC)
        payload["tests"] = SPEC["tests"][:5]
        full = json.dumps(payload)
        marker = '"tests": ['
        start = full.index(marker)
        raw = full[:start] + '"tests":[' + ",".join(json.dumps(case) for case in payload["tests"]) + ', {"args": [99, "2026-01-01"], "expected":'
        calls = []

        def truncated_once(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append(max_tokens)
            return NS(text=raw, finish_reason="length", prompt_tokens=1000, completion_tokens=6000)

        spec = expand_request("Analyze transactions by date range and status", truncated_once, attempts=1, provider_name="Groq")
        self.assertGreaterEqual(len(spec.tests), 5)
        self.assertEqual(len(spec.tests), 5)
        self.assertEqual(spec.function_name, "analyze_transactions")

    def test_python_literal_output_with_true_and_none_parses(self):
        payload = dict(SPEC)
        payload["tests"] = [dict(test) for test in SPEC["tests"][:5]]
        payload["tests"][0]["expected"] = {"ok": True, "value": None}
        literal = repr(payload)
        parsed = _extract_json("Here is the result:\n" + literal)
        self.assertIs(parsed["tests"][0]["expected"]["ok"], True)
        self.assertIsNone(parsed["tests"][0]["expected"]["value"])
        spec = expand_request(
            "Analyze transactions by date range and status",
            lambda *args, **kwargs: NS(text=literal, finish_reason="stop"),
            attempts=1,
            provider_name="Ollama",
        )
        self.assertEqual(spec.function_name, "analyze_transactions")

    def test_dual_model_uses_other_providers_spec_for_both_models(self):
        def groq_spec_failure(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            raise SpecGenerationError(
                "Groq rejected structured generation.",
                provider="Groq",
                failed_generation="not valid JSON",
            )

        def ollama_spec_success(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            return NS(text=json_reply(), finish_reason="stop", prompt_tokens=300, completion_tokens=700)

        spec, source, diagnostics = generate_shared_spec(
            "Analyze transactions by date range and status",
            {"Groq": groq_spec_failure, "Ollama": ollama_spec_success},
        )
        self.assertEqual(source, "Ollama")
        self.assertEqual(spec.function_name, "analyze_transactions")
        self.assertIn("Groq", diagnostics)
        self.assertIn("Ollama", diagnostics)

        used_prompts = {"Groq": [], "Ollama": []}

        def coding_model(provider):
            def call(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
                used_prompts[provider].append(prompt)
                return NS(
                    text="def analyze_transactions(transactions, start_date, end_date):\n    return {'income': 0, 'expense': 0}",
                    latency_seconds=0.01,
                    prompt_tokens=20,
                    completion_tokens=20,
                    model="fake",
                )
            return call

        def fake_evaluate(code, fn, tests):
            return {
                "status": "PASSED",
                "task_passed": True,
                "passed_tests": len(tests),
                "total_tests": len(tests),
                "results": [{"case": i, "passed": True, "expected": case["expected"], "actual": case["expected"], "error": None}
                            for i, case in enumerate(tests, 1)],
                "error": None,
                "exec_ms": 1.0,
                "mode": "test",
            }

        records = run_all(
            spec,
            ["zero_shot"],
            {"Groq": coding_model("Groq"), "Ollama": coding_model("Ollama")},
            fake_evaluate,
            workers=2,
        )
        self.assertEqual({row["provider"] for row in records}, {"Groq", "Ollama"})
        self.assertEqual({row["function_name"] for row in records}, {"analyze_transactions"})
        self.assertTrue(used_prompts["Groq"])
        self.assertTrue(used_prompts["Ollama"])
        self.assertTrue(all("analyze_transactions" in prompt for prompt in used_prompts["Groq"] + used_prompts["Ollama"]))


if __name__ == "__main__":
    unittest.main()
