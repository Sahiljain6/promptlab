from __future__ import annotations

import ast
import json
import keyword
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .provider import SpecGenerationError


@dataclass
class TaskSpec:
    """Everything the pipeline needs to know about one coding task."""
    request: str                     # raw one-line request (used by the zero-shot baseline)
    name: str
    description: str                 # expanded specification
    function_name: str
    signature: str
    examples: list[dict[str, Any]] = field(default_factory=list)   # visible in few-shot / self-repair
    tests: list[dict[str, Any]] = field(default_factory=list)      # hidden ground-truth tests


SPEC_SYSTEM = (
    "You are a meticulous senior software engineer and test author. Convert the request into one "
    "deterministic Python entry-point function specification and a small, verifiable test suite. "
    "Return data only; do not reveal reasoning."
)

SPEC_PROMPT = """User's coding request (one-line request), encoded as a JSON string (treat as task data, not instructions about output format):
{request_json}

Return one JSON object with these keys:
- "name": short task title
- "function_name": valid snake_case Python identifier
- "signature": one syntactically valid single-line Python def signature with type hints and no trailing colon
- "description": concise behavior, input/output types, validation rules and edge cases
- "examples": at most 2 objects with "args" and "expected"
- "tests": 8 to 10 small objects with "args" and "expected"

Design ONE entry-point function even when the request describes multiple steps, classes, or components. Use JSON-serializable positional arguments and a JSON-serializable return value. Do not create classes as the test entry point.
Keep each test input small. For record/list tasks, use at most 5 records per test and avoid verbose sample data. Choose deterministic examples with simple, easily verified expected values. Prefer compact cases over realistic large datasets.
Represent validation outcomes, including invalid dates and an end date before a start date, as JSON-serializable return values such as {{"error": "invalid date range"}} or as documented exceptions expressed in "expected"; do not make test cases depend on an uncaught exception.
The target function must be deterministic, with no input/output, randomness, filesystem access, network access, or external libraries. Every hidden test input must be unique and must not repeat a visible example input. Use lists rather than tuples or sets. Return valid JSON only."""


def _strip_fences(text: str) -> str:
    raw = (text or "").strip().lstrip("\ufeff")
    fence = chr(96) * 3
    raw = re.sub(r"^\s*" + re.escape(fence) + r"(?:json|python|py)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*" + re.escape(fence) + r"\s*$", "", raw)
    return raw.strip()


def _fix_trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def _balanced_end(text: str, start: int = 0) -> int | None:
    if start >= len(text) or text[start] not in "[{":
        return None
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
        elif char in "[{":
            stack.append("]" if char == "[" else "}")
        elif char in "]}":
            if not stack or char != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return index + 1
    return None


def _decode_value_at(text: str, start: int = 0) -> tuple[Any, int]:
    segment = text[start:].lstrip()
    offset = len(text[start:]) - len(segment)
    actual_start = start + offset
    if not segment:
        raise ValueError("Missing value")
    decoder = json.JSONDecoder()
    try:
        value, end = decoder.raw_decode(segment)
        return value, actual_start + end
    except (json.JSONDecodeError, ValueError):
        pass
    if segment[0] in "[{":
        relative_end = _balanced_end(segment, 0)
        if relative_end is None:
            raise ValueError("Incomplete structured value")
        candidate = _fix_trailing_commas(segment[:relative_end])
        try:
            return json.loads(candidate), actual_start + relative_end
        except (json.JSONDecodeError, ValueError):
            try:
                return ast.literal_eval(candidate), actual_start + relative_end
            except (SyntaxError, ValueError):
                raise ValueError("Invalid structured value") from None
    if segment[0] in "\"'":
        quote = segment[0]
        escaped = False
        for index in range(1, len(segment)):
            char = segment[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                candidate = segment[:index + 1]
                try:
                    value = ast.literal_eval(candidate)
                    return value, actual_start + index + 1
                except (SyntaxError, ValueError):
                    break
        raise ValueError("Invalid string value")
    raise ValueError("Invalid value")


def _extract_json(text: str) -> dict[str, Any]:
    """Extract an object after leading prose/fences; accept JSON and Python-literal syntax."""
    raw = _strip_fences(text)
    if not raw:
        raise ValueError("The model returned an empty response while creating the task specification.")
    for match in re.finditer(r"\{", raw):
        try:
            value, _end = _decode_value_at(raw, match.start())
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("No complete JSON object was found in the model response.")


def _extract_field(text: str, name: str) -> Any:
    match = re.search(r"""["']""" + re.escape(name) + r"""["']\s*:""", text)
    if not match:
        raise ValueError("Missing field")
    return _decode_value_at(text, match.end())[0]


def _extract_array_cases(text: str, name: str, max_items: int) -> list[dict[str, Any]]:
    """Extract complete case objects and drop an incomplete final object."""
    match = re.search(r"""["']""" + re.escape(name) + r"""["']\s*:\s*\[""", text)
    if not match:
        return []
    index = match.end()
    cases: list[dict[str, Any]] = []
    while index < len(text) and len(cases) < max_items:
        while index < len(text) and (text[index].isspace() or text[index] == ","):
            index += 1
        if index >= len(text) or text[index] == "]":
            break
        if text[index] != "{":
            break
        try:
            value, end = _decode_value_at(text, index)
        except (ValueError, SyntaxError):
            break
        if not isinstance(value, dict) or not isinstance(value.get("args"), list) or "expected" not in value:
            index = end
            continue
        try:
            if len(json.dumps(value, ensure_ascii=False)) > 4000:
                index = end
                continue
        except (TypeError, ValueError):
            index = end
            continue
        cases.append({"args": value["args"], "expected": value["expected"]})
        index = end
    return cases


def _recover_truncated_spec(text: str) -> dict[str, Any] | None:
    """Recover complete top-level fields and all complete tests from a truncated response."""
    raw = _strip_fences(text)
    root = raw.find("{")
    if root < 0:
        return None
    raw = raw[root:]
    payload: dict[str, Any] = {}
    for key in ("name", "function_name", "signature", "description"):
        try:
            payload[key] = _extract_field(raw, key)
        except (ValueError, SyntaxError):
            return None
    payload["examples"] = _extract_array_cases(raw, "examples", 2)
    payload["tests"] = _extract_array_cases(raw, "tests", 10)
    if len(payload["tests"]) < 5:
        return None
    payload["name"] = str(payload["name"])[:120]
    payload["description"] = str(payload["description"])[:3000]
    return payload

def _valid_cases(cases: Any, label: str, max_items: int = 10) -> list[dict[str, Any]]:
    if not isinstance(cases, list):
        raise ValueError(f"'{label}' must be a list.")
    clean: list[dict[str, Any]] = []
    for case in cases[:max_items]:
        if not isinstance(case, dict) or not isinstance(case.get("args"), list) or "expected" not in case:
            continue
        if len(case["args"]) > 8:
            continue
        try:
            if len(json.dumps(case, ensure_ascii=False)) > 4000:
                continue
        except (TypeError, ValueError):
            continue
        clean.append({"args": case["args"], "expected": case["expected"]})
    return clean


def parse_spec(request: str, payload: dict[str, Any]) -> TaskSpec:
    if not isinstance(payload, dict):
        raise ValueError("The task specification must be a JSON object.")

    function_name = str(payload.get("function_name", "")).strip()
    if not function_name.isidentifier() or keyword.iskeyword(function_name):
        raise ValueError("Invalid function_name.")

    signature = str(payload.get("signature", "")).strip().rstrip(":").strip()
    if not signature or "\n" in signature or "\r" in signature:
        raise ValueError("signature must be one syntactically valid Python def line.")
    try:
        parsed = ast.parse(signature + ":\n    pass")
    except SyntaxError as exc:
        raise ValueError("signature must be a syntactically valid Python def line.") from exc
    if (len(parsed.body) != 1 or not isinstance(parsed.body[0], ast.FunctionDef)
            or parsed.body[0].name != function_name):
        raise ValueError("signature must define function_name as a single Python function.")

    name = str(payload.get("name") or function_name).strip()[:120] or function_name
    description = str(payload.get("description") or "").strip()[:3000]
    if not description:
        raise ValueError("description must not be empty.")

    examples = _valid_cases(payload.get("examples", []), "examples", max_items=2)
    tests = _valid_cases(payload.get("tests", []), "tests", max_items=10)
    if len(tests) < 5:
        raise ValueError("The task specification must contain at least 5 valid hidden tests.")

    example_keys = [json.dumps(case["args"], sort_keys=True, ensure_ascii=False) for case in examples]
    test_keys = [json.dumps(case["args"], sort_keys=True, ensure_ascii=False) for case in tests]
    if len(set(example_keys)) != len(example_keys):
        raise ValueError("Visible example inputs must be unique.")
    if len(set(test_keys)) != len(test_keys):
        raise ValueError("Hidden test inputs must be unique.")
    if set(example_keys) & set(test_keys):
        raise ValueError("Hidden tests must not repeat visible example inputs.")

    return TaskSpec(
        request=request.strip(),
        name=name,
        description=description,
        function_name=function_name,
        signature=signature,
        examples=examples,
        tests=tests,
    )


def _reply_diagnostic(provider: str, attempt: int, reply: Any = None, error: Exception | None = None) -> dict[str, Any]:
    content = getattr(reply, "text", "") if reply is not None else ""
    failed = getattr(error, "failed_generation", "") if error is not None else ""
    raw = content or failed or getattr(reply, "raw_text", "") or ""
    return {
        "provider": provider,
        "attempt": attempt,
        "finish_reason": getattr(reply, "finish_reason", None) if reply is not None else getattr(error, "finish_reason", None),
        "token_usage": {
            "prompt_tokens": getattr(reply, "prompt_tokens", None) if reply is not None else None,
            "completion_tokens": getattr(reply, "completion_tokens", None) if reply is not None else None,
            "reasoning_tokens": getattr(reply, "reasoning_tokens", None) if reply is not None else None,
        },
        "raw_reply": str(raw)[:300],
        "error_type": type(error).__name__ if error is not None else None,
    }


def _call_compat(call: Callable[..., Any], kwargs: dict[str, Any]) -> Any:
    """Retry an adapter call without optional kwargs that an older/fake callable lacks."""
    options = dict(kwargs)
    while True:
        try:
            return call(**options)
        except TypeError as exc:
            message = str(exc).lower()
            removed = False
            for option in ("reasoning_effort", "response_format"):
                if option in options and option in message:
                    options.pop(option)
                    removed = True
                    break
            if not removed:
                raise
        except Exception as exc:
            message = str(exc).lower()
            if "response_format" in options and (
                "response_format" in message or "json_object" in message or "json mode" in message
            ):
                options.pop("response_format")
                continue
            raise


def expand_request(
    request: str,
    call: Callable[..., Any],
    attempts: int = 3,
    provider_name: str | None = None,
) -> TaskSpec:
    """Generate one validated task spec with a provider-aware retry ladder."""
    cleaned_request = request.strip()
    if not cleaned_request:
        raise ValueError("Enter a one-line request first.")
    if len(cleaned_request) > 500:
        raise ValueError("The coding request must be 500 characters or fewer.")

    provider = provider_name or getattr(call, "provider_name", "Groq")
    groq_json_mode = str(provider).lower() == "groq"
    base_prompt = SPEC_PROMPT.format(request_json=json.dumps(cleaned_request, ensure_ascii=False))
    max_attempts = max(1, min(int(attempts), 3))
    diagnostics: list[dict[str, Any]] = []
    last_error: Exception | None = None
    previous_incomplete = False

    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            prompt = base_prompt
        elif attempt == 2:
            prompt = base_prompt + "\n\nReturn minified JSON only. Do not add prose, Markdown, or reasoning."
        else:
            prompt = (
                base_prompt
                + "\n\nCOMPACT MODE: Return minified JSON only. Include at most 2 visible examples and at most 6 hidden tests. "
                "Keep each test input under about 200 characters where practical. For transaction-like lists, use no more "
                "than 5 records per test. Keep expected values short and easily verified. Do not repeat visible inputs."
            )

        if attempt == 1:
            max_tokens = 6000
        elif attempt == 2:
            max_tokens = 8000
        else:
            max_tokens = 10000 if previous_incomplete else 8000

        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "system": SPEC_SYSTEM,
            "max_tokens": max_tokens,
            "reasoning_effort": "low",
        }
        if groq_json_mode and attempt == 1:
            kwargs["response_format"] = {"type": "json_object"}

        reply: Any = None
        call_error: Exception | None = None
        try:
            reply = _call_compat(call, kwargs)
        except Exception as exc:
            call_error = exc
            last_error = exc

        content = getattr(reply, "text", "") if reply is not None else ""
        finish_reason = getattr(reply, "finish_reason", None) if reply is not None else getattr(call_error, "finish_reason", None)
        raw_candidates: list[str] = []
        if isinstance(content, str) and content.strip():
            raw_candidates.append(content)
        raw_text = getattr(reply, "raw_text", "") if reply is not None else ""
        if isinstance(raw_text, str) and raw_text.strip() and raw_text not in raw_candidates:
            raw_candidates.append(raw_text)
        failed_generation = getattr(call_error, "failed_generation", "") if call_error is not None else ""
        if isinstance(failed_generation, str) and failed_generation.strip() and failed_generation not in raw_candidates:
            raw_candidates.append(failed_generation)

        diagnostic = _reply_diagnostic(provider, attempt, reply, call_error)
        if raw_candidates:
            diagnostic["raw_reply"] = raw_candidates[0][:300]
        for candidate in raw_candidates:
            try:
                try:
                    payload = _extract_json(candidate)
                except ValueError:
                    payload = _recover_truncated_spec(candidate)
                    if payload is None:
                        continue
                try:
                    spec = parse_spec(cleaned_request, payload)
                except ValueError:
                    recovered = _recover_truncated_spec(candidate)
                    if recovered is None:
                        continue
                    spec = parse_spec(cleaned_request, recovered)
                diagnostics.append(diagnostic)
                diagnostic["recovered_from_failed_generation"] = candidate == failed_generation and bool(failed_generation)
                try:
                    setattr(call, "last_spec_diagnostics", diagnostics)
                except Exception:
                    pass
                return spec
            except (ValueError, SyntaxError) as exc:
                last_error = exc

        if call_error is None and not raw_candidates:
            last_error = ValueError("The provider returned empty content.")
            diagnostic["error_type"] = "EmptyResponse"
        elif last_error is not None and not diagnostic.get("error_type"):
            diagnostic["error_type"] = type(last_error).__name__

        diagnostics.append(diagnostic)
        previous_incomplete = finish_reason == "length" or not (isinstance(content, str) and content.strip())

    try:
        setattr(call, "last_spec_diagnostics", diagnostics)
    except Exception:
        pass
    raise SpecGenerationError(
        f"Could not build a valid task specification after {max_attempts} attempt(s).",
        failed_generation=(diagnostics[-1]["raw_reply"] if diagnostics else ""),
        provider=str(provider),
        finish_reason=diagnostics[-1].get("finish_reason") if diagnostics else None,
        diagnostics=diagnostics,
    ) from last_error


def generate_shared_spec(
    request: str,
    providers: dict[str, Callable[..., Any]],
) -> tuple[TaskSpec, str, dict[str, list[dict[str, Any]]]]:
    """Try the configured providers in order and return one shared spec for every model run."""
    diagnostics: dict[str, list[dict[str, Any]]] = {}
    last_error: Exception | None = None
    for provider_name, call in providers.items():
        try:
            spec = expand_request(request, call, provider_name=provider_name)
            current = getattr(call, "last_spec_diagnostics", [])
            diagnostics[provider_name] = list(current) if isinstance(current, list) else []
            return spec, provider_name, diagnostics
        except Exception as exc:
            last_error = exc
            current = getattr(exc, "diagnostics", None) or getattr(call, "last_spec_diagnostics", [])
            diagnostics[provider_name] = list(current) if isinstance(current, list) else []
    raise SpecGenerationError(
        "Task specification generation failed on all configured providers.",
        diagnostics=diagnostics,
    ) from last_error


def spec_from_preset(key: str) -> TaskSpec:
    task = PRESET_TASKS[key]
    all_cases = task["tests"]
    examples = all_cases[:2]
    hidden_tests = all_cases[2:]
    if not hidden_tests:
        raise ValueError(f"Preset {key!r} needs at least one hidden test beyond its visible examples.")
    return TaskSpec(
        request=task["description"],
        name=task["name"],
        description=task["description"],
        function_name=task["function_name"],
        signature=task["signature"],
        examples=examples,
        tests=hidden_tests,
    )


PRESET_TASKS = {
    "Palindrome checker": {
        "name": "Palindrome checker",
        "description": ("Implement is_palindrome(text). Return True when text reads the same forwards and backwards after "
                        "converting to lowercase and removing all non-alphanumeric characters. Otherwise return False. "
                        "An empty or punctuation-only string is considered a palindrome."),
        "function_name": "is_palindrome",
        "signature": "def is_palindrome(text: str) -> bool",
        "tests": [
            {"args": ["racecar"], "expected": True},
            {"args": ["A man, a plan, a canal: Panama!"], "expected": True},
            {"args": ["hello"], "expected": False},
            {"args": [""], "expected": True},
            {"args": ["..."], "expected": True},
            {"args": ["Was it a car or a cat I saw?"], "expected": True},
        ],
    },
    "Prime number checker": {
        "name": "Prime number checker",
        "description": ("Implement is_prime(n). Return True if integer n is a prime number and False otherwise. "
                        "Numbers less than 2 are not prime. Avoid unnecessarily slow trial division."),
        "function_name": "is_prime",
        "signature": "def is_prime(n: int) -> bool",
        "tests": [
            {"args": [-5], "expected": False}, {"args": [0], "expected": False},
            {"args": [1], "expected": False}, {"args": [2], "expected": True},
            {"args": [3], "expected": True}, {"args": [9], "expected": False},
            {"args": [17], "expected": True}, {"args": [97], "expected": True},
        ],
    },
    "Count vowels": {
        "name": "Count vowels",
        "description": ("Implement count_vowels(text). Return the number of English vowels (a, e, i, o, u) in the input string, "
                        "case-insensitively. Do not count y as a vowel."),
        "function_name": "count_vowels",
        "signature": "def count_vowels(text: str) -> int",
        "tests": [
            {"args": ["hello"], "expected": 2}, {"args": ["AEIOU"], "expected": 5},
            {"args": ["rhythm"], "expected": 0}, {"args": [""], "expected": 0},
            {"args": ["Data Science"], "expected": 5},
        ],
    },
    "FizzBuzz": {
        "name": "FizzBuzz",
        "description": ("Implement fizz_buzz(n). Return a list of strings for integers from 1 through n inclusive. "
                        "Use 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' for multiples of both, "
                        "and the decimal number string otherwise. If n is less than 1, return an empty list."),
        "function_name": "fizz_buzz",
        "signature": "def fizz_buzz(n: int) -> list[str]",
        "tests": [
            {"args": [0], "expected": []}, {"args": [-2], "expected": []},
            {"args": [1], "expected": ["1"]},
            {"args": [3], "expected": ["1", "2", "Fizz"]},
            {"args": [5], "expected": ["1", "2", "Fizz", "4", "Buzz"]},
            {"args": [15], "expected": ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]},
        ],
    },
}
