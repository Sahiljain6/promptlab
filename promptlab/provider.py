from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .prompts import SYSTEM_CODE_ONLY

load_dotenv()


@dataclass
class GenerationResult:
    text: str
    latency_seconds: float
    prompt_tokens: int | None
    completion_tokens: int | None
    model: str


def get_env_default(name: str, fallback: str = "") -> str:
    return os.getenv(name, fallback)


def generate_code(*, provider: str, api_key: str, model: str, prompt: str,
                  temperature: float = 0.0, custom_base_url: str = "",
                  system: str | None = None, max_tokens: int = 1500,
                  response_format: dict[str, Any] | None = None) -> GenerationResult:
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

    started = time.perf_counter()
    request_args: dict[str, Any] = {
        "model": model.strip(),
        "messages": [
            {"role": "system", "content": system or SYSTEM_CODE_ONLY},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        request_args["response_format"] = response_format
    response = client.chat.completions.create(**request_args)
    elapsed = time.perf_counter() - started
    content = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    return GenerationResult(
        text=content,
        latency_seconds=round(elapsed, 3),
        prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        model=getattr(response, "model", model.strip()),
    )
