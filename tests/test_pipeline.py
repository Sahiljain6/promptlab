import json
import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS

from promptlab.pipeline import run_all, show_outputs
from promptlab.prompts import TECHNIQUES, build_prompt, clean_generated_code
from promptlab.sandbox import evaluate_python_code
from promptlab.scoring import WEIGHT_PRESETS, pick_best, summarize
from promptlab.tasks import expand_request

SPEC = {"name": "Prime check", "function_name": "is_prime", "signature": "def is_prime(n: int) -> bool:",
        "description": "Return True if n is prime.",
        "examples": [{"args": [2], "expected": True}, {"args": [4], "expected": False}],
        "tests": [{"args": [a], "expected": e} for a, e in
                  [(-1, False), (0, False), (1, False), (3, True), (4, False), (17, True), (97, True), (100, False)]]
        + [{"args": [7], "expected": False}]}  # wrong on purpose (7 is prime): every candidate fails it
GOOD = "def is_prime(n):\n    if n < 2:\n        return False\n    i = 2\n    while i * i <= n:\n        if n % i == 0:\n            return False\n        i += 1\n    return True\n"
BUGGY = "def is_prime(n):\n    return n > 1\n"


def fake_llm(prompt, system=None, max_tokens=1500):
    if "One-line request" in prompt:
        return NS(text=json.dumps(SPEC), latency_seconds=0.1, prompt_tokens=10, completion_tokens=10, model="fake")
    zero_shot = prompt.startswith("Task:") and "Required function signature" not in prompt and "Input/output" not in prompt
    first_repair_round = ("Required function signature" in prompt and "docstring" not in prompt
                          and "Implementation checklist" not in prompt and "privately" not in prompt and "Your previous" not in prompt
                          and "Reason" not in prompt and "numbered plan" not in prompt)
    code = BUGGY if (zero_shot or first_repair_round) else GOOD
    if "Your previous attempt" in prompt:
        code = GOOD
    return NS(text="Reasoning\n```python\n" + code + "```", latency_seconds=0.2, prompt_tokens=100, completion_tokens=50, model="fake")


def local_eval(code, fn, tests):
    # Explicitly opt in only within tests; the web app never exposes this unsafe executor.
    with patch.dict(os.environ, {"PROMPTLAB_ALLOW_UNSAFE_LOCAL_EXECUTOR": "true"}):
        return evaluate_python_code(code, fn, tests, timeout_seconds=10, mode="local")


class PromptTests(unittest.TestCase):
    def test_all_techniques_build_a_prompt(self):
        for technique in TECHNIQUES:
            with self.subTest(technique=technique.key):
                prompt = build_prompt(technique.key, "Count vowels", "Count vowels in a string.", "count_vowels",
                                      "def count_vowels(text: str) -> int", examples=[{"args": ["hi"], "expected": 1}])
                self.assertIn("count_vowels", prompt)
                self.assertIn("Python", prompt)

    def test_zero_shot_is_the_bare_request(self):
        prompt = build_prompt("zero_shot", "n", "long spec", "f", "def f(x)", request="do the thing")
        self.assertIn("do the thing", prompt)
        self.assertNotIn("long spec", prompt)
        self.assertNotIn("def f(x)", prompt)

    def test_unknown_technique_raises(self):
        with self.assertRaises(ValueError):
            build_prompt("not-a-technique", "t", "d", "f", "def f()")

    def test_picks_function_block_from_reasoning_reply(self):
        text = "Plan:\n```python\nx = 1\n```\nFinal:\n```python\ndef solve(a):\n    return a\n```"
        self.assertIn("def solve", clean_generated_code(text, "solve"))

    def test_removes_intro_text_when_unfenced(self):
        self.assertTrue(clean_generated_code("Here is the solution:\n\ndef solve(x):\n    return x + 1").startswith("def solve"))


class PipelineTests(unittest.TestCase):
    def test_expand_request_parses_fenced_json_and_validates(self):
        spec = expand_request("check prime", fake_llm)
        self.assertEqual(spec.function_name, "is_prime")
        self.assertFalse(spec.signature.endswith(":"))
        with self.assertRaises(ValueError):
            expand_request("x", lambda *a, **k: NS(text="not json"))

    def test_full_run_ranks_and_flags_suspect_tests(self):
        spec = expand_request("check prime", fake_llm)
        records = run_all(spec, [t.key for t in TECHNIQUES], fake_llm, local_eval, workers=2)
        self.assertEqual(len(records), len(TECHNIQUES))
        self.assertEqual(records[0]["adj_total"], 8)           # the wrong test was excluded
        rows = summarize(records, WEIGHT_PRESETS["Accuracy first"])
        top, best = pick_best(rows, records)
        self.assertNotEqual(top["technique_key"], "zero_shot")  # buggy baseline must not win
        zero = next(r for r in rows if r["technique_key"] == "zero_shot")
        self.assertLess(zero["accuracy"], 1.0)
        repaired = next(r for r in records if r["technique_key"] == "self_repair")
        self.assertEqual(repaired["rounds"], 2)
        self.assertTrue(repaired["solved"])
        out = show_outputs(best["generated_code"], spec, local_eval, extra_args=[13])
        self.assertEqual(out[-1]["output"], "True")

    def test_auto_mode_does_not_fall_back_to_host_execution(self):
        with patch("promptlab.sandbox.docker_available", return_value=False):
            result = evaluate_python_code(
                "def is_prime(n): return True\n",
                "is_prime",
                [{"args": [3], "expected": True}],
                mode="auto",
            )
        self.assertEqual(result["status"], "NOT TESTED")
        self.assertIn("will not fall back", result["error"])

    def test_local_executor_is_disabled_without_explicit_flag(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PROMPTLAB_ALLOW_UNSAFE_LOCAL_EXECUTOR", None)
            result = evaluate_python_code(
                "def is_prime(n): return True\n",
                "is_prime",
                [{"args": [3], "expected": True}],
                mode="local",
            )
        self.assertEqual(result["status"], "NOT TESTED")
        self.assertIn("disabled by default", result["error"])

    def test_executor_handles_bad_code(self):
        tests = [{"args": [3], "expected": True}]
        self.assertEqual(evaluate_python_code("def f(:\n", "is_prime", tests, mode="local")["status"], "SYNTAX ERROR")
        self.assertEqual(evaluate_python_code("import os\ndef is_prime(n): return True\n", "is_prime", tests, mode="local")["status"], "BLOCKED")
        self.assertEqual(evaluate_python_code("def is_prime(n):\n    while True: pass\n", "is_prime", tests, timeout_seconds=3, mode="local")["status"], "TIMEOUT")


    def test_dual_model_run_compares_provider_and_technique_pairs(self):
        spec = expand_request("check prime", fake_llm)
        clients = {"Groq": fake_llm, "Gemini": fake_llm}
        records = run_all(spec, ["zero_shot", "function_signature"], clients, local_eval, workers=4)
        self.assertEqual(len(records), 4)
        self.assertEqual({r["provider"] for r in records}, {"Groq", "Gemini"})
        rows = summarize(records, WEIGHT_PRESETS["Accuracy first"])
        self.assertEqual(len(rows), 4)
        top, best = pick_best(rows, records)
        self.assertEqual(best["provider"], top["provider"])
        self.assertEqual(top["comparison_key"], f'{best["provider"]}::{best["technique_key"]}')


if __name__ == "__main__":
    unittest.main()
