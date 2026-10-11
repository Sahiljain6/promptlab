import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from promptlab.provider import generate_code


class ProviderResponseFormatTests(unittest.TestCase):
    def test_generate_code_forwards_json_mode(self):
        create = Mock(return_value=NS(
            choices=[NS(message=NS(content='{"ok": true}'))],
            usage=NS(prompt_tokens=12, completion_tokens=5),
            model="test-model",
        ))
        client = NS(chat=NS(completions=NS(create=create)))

        with patch("promptlab.provider.OpenAI", return_value=client):
            result = generate_code(
                provider="Groq",
                api_key="test-key",
                model="openai/gpt-oss-20b",
                prompt="Return a JSON object.",
                response_format={"type": "json_object"},
            )

        self.assertEqual(result.text, '{"ok": true}')
        self.assertEqual(result.prompt_tokens, 12)
        self.assertEqual(create.call_args.kwargs["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
