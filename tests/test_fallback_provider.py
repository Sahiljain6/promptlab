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
            {
                "case": index,
                "passed": True,
                "expected": case["expected"],
                "actual": case["expected"],
                "error": None,
            }
            for index, case in enumerate(tests, 1)
        ],
        "error": None,
        "exec_ms": 0.1,
        "mode": "fake",
    }


def failing_provider(name, calls):
    def call(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
        calls.append(name)
        raise RuntimeError(f"{name} unavailable")

    return call


class PrimaryAndBackupProviderTests(unittest.TestCase):
    def test_groq_spec_success_keeps_gemini_and_ollama_idle(self):
        calls = []

        def groq(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append("Groq")
            return generation(json.dumps(SPEC))

        def unused(name):
            def call(*args, **kwargs):
                self.fail(f"{name} must remain idle when Groq produces a valid specification")
            return call

        spec, source, _ = generate_shared_spec(
            "Create a prime checker",
            {"Groq": groq, "Gemini": unused("Gemini"), "Ollama": unused("Ollama")},
        )

        self.assertEqual(spec.function_name, "is_prime")
        self.assertEqual(source, "Groq")
        self.assertEqual(calls, ["Groq"])

    def test_gemini_spec_is_second_choice_after_groq_fails(self):
        calls = []

        def gemini(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append("Gemini")
            return generation(json.dumps(SPEC))

        def unused_ollama(*args, **kwargs):
            self.fail("Ollama must remain idle when Gemini produces a valid specification")

        spec, source, diagnostics = generate_shared_spec(
            "Create a prime checker",
            {
                "Groq": failing_provider("Groq", calls),
                "Gemini": gemini,
                "Ollama": unused_ollama,
            },
        )

        self.assertEqual(spec.function_name, "is_prime")
        self.assertEqual(source, "Gemini")
        self.assertIn("Groq", diagnostics)
        self.assertEqual(calls, ["Groq", "Gemini"])

    def test_ollama_spec_fallback_runs_only_after_both_primary_providers_fail(self):
        calls = []

        def ollama(prompt, system=None, max_tokens=1500, response_format=None, reasoning_effort=None):
            calls.append("Ollama")
            return generation(json.dumps(SPEC))

        spec, source, diagnostics = generate_shared_spec(
            "Create a prime checker",
            {
                "Groq": failing_provider("Groq", calls),
                "Gemini": failing_provider("Gemini", calls),
                "Ollama": ollama,
            },
        )

        self.assertEqual(spec.function_name, "is_prime")
        self.assertEqual(source, "Ollama")
        self.assertEqual(set(calls), {"Groq", "Gemini", "Ollama"})
        self.assertIn("Groq", diagnostics)
        self.assertIn("Gemini", diagnostics)

    def test_ollama_code_fallback_runs_only_when_both_primary_calls_fail(self):
        spec = parse_spec("Create a prime checker", SPEC)
        fallback_calls = []

        def ollama(prompt, system=None, max_tokens=1500):
            fallback_calls.append(prompt)
            return generation("def is_prime(n):\n    return n > 1\n")

        records = run_all(
            spec,
            ["zero_shot"],
            {
                "Groq": failing_provider("Groq", []),
                "Gemini": failing_provider("Gemini", []),
            },
            evaluator,
            workers=2,
            fallback_llm=ollama,
            fallback_provider_name="Ollama (fallback)",
        )

        self.assertEqual(len(fallback_calls), 1)
        self.assertEqual(len(records), 3)
        fallback = next(record for record in records if record["provider"] == "Ollama (fallback)")
        self.assertEqual(fallback["status"], "PASSED")

    def test_ollama_stays_idle_when_either_primary_provider_returns_code(self):
        spec = parse_spec("Create a prime checker", SPEC)
        fallback_calls = []

        def groq(prompt, system=None, max_tokens=1500):
            return generation("def is_prime(n):\n    return n > 1\n")

        def ollama(prompt, system=None, max_tokens=1500):
            fallback_calls.append(prompt)
            self.fail("Ollama must remain idle when one primary provider returns a response")

        records = run_all(
            spec,
            ["zero_shot"],
            {
                "Groq": groq,
                "Gemini": failing_provider("Gemini", []),
            },
            evaluator,
            workers=2,
            fallback_llm=ollama,
            fallback_provider_name="Ollama (fallback)",
        )

        self.assertEqual(fallback_calls, [])
        self.assertEqual(len(records), 2)
        self.assertNotIn("Ollama (fallback)", {record["provider"] for record in records})

    def test_empty_primary_response_counts_as_api_error_for_backup_decision(self):
        spec = parse_spec("Create a prime checker", SPEC)
        fallback_calls = []

        def empty_groq(prompt, system=None, max_tokens=1500):
            return generation("  ")

        def ollama(prompt, system=None, max_tokens=1500):
            fallback_calls.append(prompt)
            return generation("def is_prime(n):\n    return n > 1\n")

        records = run_all(
            spec,
            ["zero_shot"],
            {
                "Groq": empty_groq,
                "Gemini": failing_provider("Gemini", []),
            },
            evaluator,
            workers=2,
            fallback_llm=ollama,
            fallback_provider_name="Ollama (fallback)",
        )

        self.assertEqual(len(fallback_calls), 1)
        self.assertTrue(any(record["provider"] == "Ollama (fallback)" for record in records))


if __name__ == "__main__":
    unittest.main()
