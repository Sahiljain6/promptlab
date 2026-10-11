from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

from .prompts import SYSTEM_CODE_ONLY

load_dotenv()


class SpecGenerationError(ValueError):
    """Safe provider/specification error with optional recoverable model output."""

    def __init__(
        self,
        message: str,
        *,
        failed_generation: str = "",
        provider: str = "",
        finish_reason: str | None = None,
        diagnostics: dict[str, Any] | list[dict[str, Any]] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failed_generation = failed_generation or ""
        self.provider = provider
        self.finish_reason = finish_reason
        self.diagnostics = diagnostics if diagnostics is not None else []
        self.status_code = status_code


@dataclass
class GenerationResult:
    text: str
    latency_seconds: float
    prompt_tokens: int | None
    completion_tokens: int | None
    model: str
    finish_reason: str | None = None
    reasoning_text: str = ""
    reasoning_tokens: int | None = None
    raw_text: str = ""


def get_env_default(name: str, fallback: str = "") -> str:
    return os.getenv(name, fallback)


def _failed_generation_from_body(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    error = body.get("error", body)
    if not isinstance(error, dict):
        return ""
    value = error.get("failed_generation", "")
    return value if isinstance(value, str) else ""


def generate_code(
    *,
    provider: str,
    api_key: str,
    model: str,
    prompt: str,
    temperature: float = 0.0,
    custom_base_url: str = "",
    system: str | None = None,
    max_tokens: int = 1500,
    response_format: dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
) -> GenerationResult:
    if not api_key.strip():
        raise ValueError("No API key configured. Set it in your .env file or Streamlit Secrets.")
    if not model.strip():
        raise ValueError("Enter a model ID.")

    provider = provider.strip()
    if provider == "Groq":
        base_url = "https://api.groq.com/openai/v1"
    elif provider == "OpenAI":
        base_url = None
    else:
        base_url = custom_base_url.strip() or None
        if base_url is None:
            raise ValueError("Enter the base URL for your OpenAI-compatible provider.")

    kwargs: dict[str, Any] = {"api_key": api_key.strip(), "timeout": 90.0, "max_retries": 2}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)

    request_args: dict[str, Any] = {
        "model": model.strip(),
        "messages": [
            {"role": "system", "content": system or SYSTEM_CODE_ONLY},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # JSON mode is used only for Groq. Ollama Cloud's compatibility layer can return an
    # empty message or reject this option for reasoning models.
    if response_format is not None and provider == "Groq":
        request_args["response_format"] = response_format
    if reasoning_effort:
        # extra_body is supported by older OpenAI SDK releases and avoids adding a
        # version-specific top-level SDK parameter.
        request_args["extra_body"] = {"reasoning_effort": reasoning_effort}

    started = time.perf_counter()
    try:
        response = client.chat.completions.create(**request_args)
    except BadRequestError as exc:
        failed_generation = _failed_generation_from_body(getattr(exc, "body", None))
        raise SpecGenerationError(
            "Provider rejected the generation request.",
            failed_generation=failed_generation,
            provider=provider,
            status_code=getattr(exc, "status_code", None),
        ) from exc
    elapsed = time.perf_counter() - started

    choice = response.choices[0] if getattr(response, "choices", None) else None
    message = getattr(choice, "message", None) if choice else None
    content = getattr(message, "content", None) if message else None
    # Reasoning is deliberately returned separately; it is never used as generated answer text.
    reasoning_parts = [
        getattr(message, "reasoning", None) if message else None,
        getattr(message, "reasoning_content", None) if message else None,
    ]
    reasoning_text = "\n".join(part for part in reasoning_parts if isinstance(part, str) and part.strip())
    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None) if usage else None
    reasoning_tokens = getattr(details, "reasoning_tokens", None) if details else None
    return GenerationResult(
        text=content if isinstance(content, str) else "",
        latency_seconds=round(elapsed, 3),
        prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        model=getattr(response, "model", model.strip()),
        finish_reason=getattr(choice, "finish_reason", None) if choice else None,
        reasoning_text=reasoning_text,
        reasoning_tokens=reasoning_tokens,
        raw_text=content if isinstance(content, str) else "",
    )
