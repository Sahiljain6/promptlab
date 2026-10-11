from __future__ import annotations

import json
import keyword
import re
from dataclasses import dataclass, field
from typing import Any, Callable


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


SPEC_SYSTEM = ("You are a meticulous senior software engineer and test author. You turn a one-line request into a precise "
               "Python function specification and a hidden test suite. Respond with one valid JSON object only.")

SPEC_PROMPT = """One-line request: \"{request}\"

Return ONLY a JSON object with these keys:
- "name": short task title
- "function_name": snake_case Python identifier
- "signature": a single `def` line with type hints and NO trailing colon, e.g. def is_prime(n: int) -> bool
- "description": 2-4 sentences giving exact behaviour, input/output types and edge-case rules
- "examples": exactly 2 objects {{"args": [...], "expected": ...}}
- "tests": 8 to 10 objects of the same shape that cover normal cases, boundaries and edge cases

Rules: "args" is a JSON list of positional arguments; "expected" is a JSON value (use lists, never tuples or sets);
the function must be deterministic with no input/output, randomness or imports of external libraries. Work out every
expected value by hand and double-check it. Do not repeat the examples inside "tests"."""


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("The model did not return a JSON object.")
    return json.loads(text[start:end + 1])


def _valid_cases(cases: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"'{label}' must be a non-empty list.")
    clean = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("args"), list) or "expected" not in case:
            raise ValueError(f"Every item in '{label}' needs an 'args' list and an 'expected' value.")
        clean.append({"args": case["args"], "expected": case["expected"]})
    return clean


def parse_spec(request: str, payload: dict[str, Any]) -> TaskSpec:
    function_name = str(payload.get("function_name", "")).strip()
    if not function_name.isidentifier() or keyword.iskeyword(function_name):
        raise ValueError(f"Invalid function_name: {function_name!r}")
    signature = str(payload.get("signature", "")).strip().rstrip(":").strip()
    if not re.match(rf"def\s+{re.escape(function_name)}\s*\(", signature):
        raise ValueError("signature must be a def line for function_name.")
    return TaskSpec(
        request=request.strip(),
        name=str(payload.get("name") or function_name).strip(),
        description=str(payload.get("description", "")).strip() or request.strip(),
        function_name=function_name,
        signature=signature,
        examples=_valid_cases(payload.get("examples"), "examples")[:3],
        tests=_valid_cases(payload.get("tests"), "tests"),
    )


def expand_request(request: str, call: Callable[..., Any], attempts: int = 2) -> TaskSpec:
    """Convert a one-line request into a TaskSpec using an LLM.

    `call(prompt, system=..., max_tokens=...)` must return an object with a `.text` attribute.
    """
    if not request.strip():
        raise ValueError("Enter a one-line request first.")
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            reply = call(SPEC_PROMPT.format(request=request.strip().replace('"', "'")), system=SPEC_SYSTEM, max_tokens=3000)
            return parse_spec(request, _extract_json(reply.text))
        except Exception as exc:  # malformed JSON, bad schema, API hiccup
            last_error = exc
    raise ValueError(f"Could not build a task specification from that request: {last_error}")


def spec_from_preset(key: str) -> TaskSpec:
    task = PRESET_TASKS[key]
    return TaskSpec(request=task["description"], name=task["name"], description=task["description"],
                    function_name=task["function_name"], signature=task["signature"],
                    examples=task["tests"][:2], tests=task["tests"])


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
