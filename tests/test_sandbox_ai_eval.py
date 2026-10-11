import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from promptlab.sandbox import _evaluate_with_groq


def response(text):
    return NS(choices=[NS(message=NS(content=text))])


class AIEvaluatorReliabilityTests(unittest.TestCase):
    def test_invalid_json_is_retried_and_booleans_are_strict(self):
        create = Mock(side_effect=[
            response("Here is my analysis, not JSON."),
            response(json.dumps({
                "results": [
                    {"case": 1, "passed": True, "actual": 4, "error": None},
                    {"case": 2, "passed": "true", "actual": 8, "error": None},
                ]
            })),
        ])
        client = NS(chat=NS(completions=NS(create=create)))
        with patch("promptlab.sandbox.OpenAI", return_value=client):
            result = _evaluate_with_groq(
                "def square(n): return n*n",
                "square",
                [{"args": [2], "expected": 4}, {"args": [3], "expected": 9}],
                "fake-token",
                "fake-model",
                1,
            )

        self.assertEqual(create.call_count, 2)
        self.assertEqual(create.call_args_list[0].kwargs["response_format"], {"type": "json_object"})
        self.assertEqual(result["status"], "AI FAIL")
        self.assertEqual([x["passed"] for x in result["results"]], [True, False])
        self.assertIn("did not execute", result["error"])

    def test_unsupported_json_mode_retries_without_response_format(self):
        create = Mock(side_effect=[
            ValueError("response_format json_object unsupported"),
            response(json.dumps({"results": [{"case": 1, "passed": True, "actual": 4, "error": None}]})),
        ])
        client = NS(chat=NS(completions=NS(create=create)))
        with patch("promptlab.sandbox.OpenAI", return_value=client):
            result = _evaluate_with_groq(
                "def square(n): return n*n",
                "square",
                [{"args": [2], "expected": 4}],
                "fake-token",
                "fake-model",
                1,
            )

        self.assertEqual(create.call_count, 2)
        self.assertEqual(create.call_args_list[0].kwargs["response_format"], {"type": "json_object"})
        self.assertNotIn("response_format", create.call_args_list[1].kwargs)
        self.assertEqual(result["status"], "AI PASS")


if __name__ == "__main__":
    unittest.main()
