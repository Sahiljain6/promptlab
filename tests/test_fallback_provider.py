import json
import unittest
from types import SimpleNamespace as NS

from promptlab.pipeline import run_all
from promptlab.tasks import generate_shared_spec, parse_spec


SPEC = {
    "name": "Prime checker",
    "function_name": "is_prime",
    "signature": "def is_prime(n: int) -> bool",
    "description": "Return True only for prime integers greater than one.",
    "examples": [{"args": [2], "expected": True}, {"args": [4], "expected": False}],
    "tests": [
        {"args": [-1], "expected": False},
        {"args": [0], "expected": False},
        {"args": [1], "expected": False},
        {"args": [3], "expected": True},
        {"args": [5], "expected": True},
        {"args": [7], "expected": True},
    ],
}


def generation(text):
    return NS(
        text=text,
        latency_seconds=0.01,
        prompt_tokens=20,
        completion_tokens=15,
        model="fake-model",
    )


def evaluator(code, function_name, tests):
    return {
        "status": "PASSED",
        "task_passed": True,
        "passed_tests": len(tests),
        "total_tests": len(tests),
        "results": [
            {"case": index, "passed": True, "expected": case["expected"], "actual": case["expected"], "error": None}
            for index, case in enumerate(tests, 1)
        ],
        "error": None,
        "exec_ms": 0.1,
        "mode": "fake",
    }


class GeminiFallbackTests(unittest.TestCase):
    def test_gemini_spec_fallback_is_called_only_after_groq_and_ollama_fail(self):
        call_order = []

        def failing_provider(name):
            def call(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
                call_order.append(name)
                raise RuntimeError(f"{name} unavailable")
            return call

        def gemini(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            call_order.append("Gemini")
            return generation(json.dumps(SPEC))

        spec, source, diagnostics = generate_shared_spec(
            "Create a prime checker",
            {
                "Groq": failing_provider("Groq"),
                "Ollama": failing_provider("Ollama"),
                "Gemini": gemini,
            },
        )
        self.assertEqual(spec.function_name, "is_prime")
        self.assertEqual(source, "Gemini")
        self.assertIn("Groq", diagnostics)
        self.assertIn("Ollama", diagnostics)
        self.assertEqual(call_order[-1], "Gemini")
        self.assertEqual(call_order.count("Gemini"), 1)
        gemini_index = call_order.index("Gemini")
        self.assertIn("Groq", call_order[:gemini_index])
        self.assertIn("Ollama", call_order[:gemini_index])
        self.assertTrue(all(name != "Gemini" for name in call_order[:gemini_index]))

    def test_gemini_spec_fallback_stays_idle_when_ollama_recovers(self):
        calls = []

        def groq(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append("Groq")
            raise RuntimeError("Groq unavailable")

        def ollama(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append("Ollama")
            return generation(json.dumps(SPEC))

        def gemini(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append("Gemini")
            raise AssertionError("Gemini must remain idle when Ollama succeeds")

        _, source, _ = generate_shared_spec(
            "Create a prime checker",
            {"Groq": groq, "Ollama": ollama, "Gemini": gemini},
        )
        self.assertEqual(source, "Ollama")
        self.assertNotIn("Gemini", calls)

    def test_gemini_code_fallback_runs_only_when_both_primary_calls_fail(self):
        gemini_calls = []

        def failed(prompt, system=None, max_tokens=1500):
            raise RuntimeError("provider unavailable")

        def gemini(prompt, system=None, max_tokens=1500):
            gemini_calls.append(prompt)
            return generation("def is_prime(n):\n    return n > 1\n")

        spec = parse_spec("Create a prime checker", SPEC)
        records = run_all(
            spec,
            ["zero_shot"],
            {"Groq": failed, "Ollama": failed},
            evaluator,
            workers=2,
            fallback_llm=gemini,
            fallback_provider_name="Gemini (fallback)",
        )
        self.assertEqual(len(gemini_calls), 1)
        self.assertEqual(len(records), 3)
        fallback = next(record for record in records if record["provider"] == "Gemini (fallback)")
        self.assertEqual(fallback["status"], "PASSED")

    def test_empty_primary_response_counts_as_api_error_and_uses_gemini(self):
        gemini_calls = []

        def empty_groq(prompt, system=None, max_tokens=1500):
            return generation("  ")

        def failed_ollama(prompt, system=None, max_tokens=1500):
            raise RuntimeError("Ollama unavailable")

        def gemini(prompt, system=None, max_tokens=1500):
            gemini_calls.append(prompt)
            return generation("def is_prime(n):\n    return n > 1\n")

        spec = parse_spec("Create a prime checker", SPEC)
        records = run_all(
            spec,
            ["zero_shot"],
            {"Groq": empty_groq, "Ollama": failed_ollama},
            evaluator,
            workers=2,
            fallback_llm=gemini,
        )
        self.assertEqual(len(gemini_calls), 1)
        self.assertTrue(any(record["provider"] == "Gemini (fallback)" for record in records))

    def test_gemini_code_fallback_stays_idle_if_one_primary_succeeds(self):
        gemini_calls = []

        def groq(prompt, system=None, max_tokens=1500):
            return generation("def is_prime(n):\n    return n > 1\n")

        def failed_ollama(prompt, system=None, max_tokens=1500):
            raise RuntimeError("Ollama unavailable")

        def gemini(prompt, system=None, max_tokens=1500):
            gemini_calls.append(prompt)
            return generation("def is_prime(n):\n    return n > 1\n")

        spec = parse_spec("Create a prime checker", SPEC)
        records = run_all(
            spec,
            ["zero_shot"],
            {"Groq": groq, "Ollama": failed_ollama},
            evaluator,
            workers=2,
            fallback_llm=gemini,
        )
        self.assertEqual(len(gemini_calls), 0)
        self.assertEqual(len(records), 2)


if __name__ == "__main__":
    unittest.main()
