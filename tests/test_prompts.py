import ast
import unittest

from promptlab.prompts import TECHNIQUES, build_prompt, clean_generated_code


class PromptTests(unittest.TestCase):
    def test_all_techniques_build_a_prompt(self):
        for technique in TECHNIQUES:
            with self.subTest(technique=technique.key):
                prompt = build_prompt(technique.key, "Count vowels", "Count vowels in a string.", "count_vowels", "def count_vowels(text: str) -> int")
                self.assertIn("count_vowels", prompt)
                self.assertIn("Python", prompt)

    def test_unknown_technique_raises(self):
        with self.assertRaises(ValueError):
            build_prompt("not-a-technique", "t", "d", "f", "def f()")

    def test_removes_markdown_fence(self):
        code = clean_generated_code("Here is the code:\n```python\ndef is_prime(n):\n    return n > 1\n```")
        ast.parse(code)
        self.assertIn("def is_prime", code)
        self.assertNotIn("```", code)

    def test_removes_intro_text_when_unfenced(self):
        code = clean_generated_code("Here is the solution:\n\ndef solve(x):\n    return x + 1")
        ast.parse(code)
        self.assertTrue(code.startswith("def solve"))


if __name__ == "__main__":
    unittest.main()
