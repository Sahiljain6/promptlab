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

    def test_ollama_cloud_uses_openai_compatible_endpoint(self):
        create = Mock(return_value=NS(
            choices=[NS(message=NS(content='{"ok": true}'))],
            usage=NS(prompt_tokens=12, completion_tokens=5),
            model="gpt-oss:20b-cloud",
        ))
        client = NS(chat=NS(completions=NS(create=create)))

        with patch("promptlab.provider.OpenAI", return_value=client) as factory:
            result = generate_code(
                provider="Custom OpenAI-compatible",
                api_key="test-key",
                model="gpt-oss:20b-cloud",
                prompt="Return a JSON object.",
                custom_base_url="https://ollama.com/v1",
                response_format={"type": "json_object"},
            )

        self.assertEqual(result.model, "gpt-oss:20b-cloud")
        self.assertEqual(factory.call_args.kwargs["base_url"], "https://ollama.com/v1")
        self.assertNotIn("response_format", create.call_args.kwargs)


    def test_gemini_backup_uses_google_openai_compatible_endpoint(self):
        create = Mock(return_value=NS(
            choices=[NS(message=NS(content='{"ok": true}'), finish_reason="stop")],
            usage=NS(prompt_tokens=12, completion_tokens=5),
            model="gemini-3.8-flash",
        ))
        client = NS(chat=NS(completions=NS(create=create)))

        with patch("promptlab.provider.OpenAI", return_value=client) as factory:
            result = generate_code(
                provider="Gemini",
                api_key="test-gemini-key",
                model="gemini-3.8-flash",
                prompt="Return a JSON object.",
                custom_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                response_format={"type": "json_object"},
                reasoning_effort="low",
            )

        self.assertEqual(result.model, "gemini-3.8-flash")
        self.assertEqual(
            factory.call_args.kwargs["base_url"],
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.assertNotIn("response_format", create.call_args.kwargs)
        self.assertEqual(create.call_args.kwargs["extra_body"], {"reasoning_effort": "low"})

if __name__ == "__main__":
    unittest.main()
