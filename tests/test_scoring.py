import unittest

from promptlab.scoring import annotate, flag_suspect_tests, summarize


class ScoringReliabilityTests(unittest.TestCase):
    def test_ai_estimates_are_not_used_to_mark_hidden_tests_suspect(self):
        records = [
            {
                "status": "AI FAIL",
                "total_tests": 1,
                "test_results": [{"case": 1, "passed": False}],
            }
            for _ in range(5)
        ]
        self.assertEqual(flag_suspect_tests(records), set())

    def test_api_failures_do_not_receive_a_positive_composite_score(self):
        records = [{
            "provider": "Groq",
            "technique_key": "few_shot",
            "technique_name": "Few-shot",
            "status": "API ERROR",
            "total_tests": 8,
            "test_results": [],
            "adj_rate": 0.0,
            "solved": False,
            "latency_seconds": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "exec_ms": None,
        }]
        annotate(records, set())
        rows = summarize(records, (0.70, 0.10, 0.10, 0.10))
        self.assertEqual(rows[0]["valid_trials"], 0)
        self.assertEqual(rows[0]["score"], 0.0)
        self.assertEqual(rows[0]["accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
