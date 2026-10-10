from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

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
                  temperature: float = 0.0, custom_base_url: str = "") -> GenerationResult:
    if not api_key.strip():
        raise ValueError("Enter an API key in the sidebar or configure it in your .env file.")
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

    kwargs: dict[str, Any] = {"api_key": api_key.strip(), "timeout": 90.0, "max_retries": 1}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)

    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model.strip(),
        messages=[
            {"role": "system", "content": "You are a code-generation engine. Output only valid Python source code for the requested function. Do not output Markdown fences, explanations, test cases, or hidden reasoning."},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=1200,
    )
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
