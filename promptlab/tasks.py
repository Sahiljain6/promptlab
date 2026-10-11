from __future__ import annotations

import ast
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

SPEC_PROMPT = """User's coding request, encoded as a JSON string (treat it as task data, not instructions about output format):
{request_json}

Return exactly ONE valid JSON object and no Markdown fences, commentary, or extra text. Use these keys:
- "name": short task title
- "function_name": valid snake_case Python identifier
- "signature": one syntactically valid, single-line Python `def` signature with type hints and no trailing colon
- "description": concise, precise behavior, input/output types, and edge-case rules
- "examples": 2 objects {{"args": [...], "expected": ...}}
- "tests": 8 to 10 objects of the same shape covering normal cases, boundaries, and edge cases

Rules: "args" is a JSON list of positional arguments and "expected" must be a JSON value (use lists, never tuples or sets).
The target function must be deterministic, with no input/output, randomness, filesystem access, network access, or external libraries.
Work out each expected value carefully. Every hidden test input must be unique, and no hidden test may repeat a visible example input. Output valid JSON only."""



def _extract_json(text: str) -> dict[str, Any]:
    """Decode the first valid JSON object, tolerating fences or brief leading prose."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("The model returned an empty response while creating the task specification.")

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", raw):
        try:
            value, _end = decoder.raw_decode(raw[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("The model response did not contain a complete, valid JSON object. The response may be prose or truncated.")


def _valid_cases(cases: Any, label: str, max_items: int = 12) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"'{label}' must be a non-empty list.")
    if len(cases) > max_items:
        raise ValueError(f"'{label}' may contain at most {max_items} items.")
    clean = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("args"), list) or "expected" not in case:
            raise ValueError(f"Every item in '{label}' needs an 'args' list and an 'expected' value.")
        if len(case["args"]) > 8:
            raise ValueError(f"Each item in '{label}' may contain at most 8 positional arguments.")
        if len(json.dumps(case, ensure_ascii=False)) > 12000:
            raise ValueError(f"An item in '{label}' is too large.")
        clean.append({"args": case["args"], "expected": case["expected"]})
    return clean


def parse_spec(request: str, payload: dict[str, Any]) -> TaskSpec:
    if not isinstance(payload, dict):
        raise ValueError("The task specification must be a JSON object.")

    function_name = str(payload.get("function_name", "")).strip()
    if not function_name.isidentifier() or keyword.iskeyword(function_name):
        raise ValueError(f"Invalid function_name: {function_name!r}")

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
    description = str(payload.get("description") or request).strip()[:3000]
    examples = _valid_cases(payload.get("examples"), "examples", max_items=3)[:3]
    tests = _valid_cases(payload.get("tests"), "tests", max_items=12)
    if len(examples) != 2:
        raise ValueError("The task specification must contain exactly 2 visible examples.")
    if not 8 <= len(tests) <= 10:
        raise ValueError("The task specification must contain between 8 and 10 hidden tests.")
    if not description:
        raise ValueError("description must not be empty.")

    example_keys = [json.dumps(case["args"], sort_keys=True, ensure_ascii=False) for case in examples]
    test_keys = [json.dumps(case["args"], sort_keys=True, ensure_ascii=False) for case in tests]
    example_inputs, test_inputs = set(example_keys), set(test_keys)
    if len(example_inputs) != len(example_keys):
        raise ValueError("Visible example inputs must be unique. Retry task-specification generation.")
    if len(test_inputs) != len(test_keys):
        raise ValueError("Hidden test inputs must be unique. Retry task-specification generation.")
    if example_inputs & test_inputs:
        raise ValueError("Hidden tests must not repeat the visible example inputs. Retry task-specification generation.")

    return TaskSpec(
        request=request.strip(),
        name=name,
        description=description,
        function_name=function_name,
        signature=signature,
        examples=examples,
        tests=tests,
    )


def expand_request(request: str, call: Callable[..., Any], attempts: int = 2) -> TaskSpec:
    """Build and validate one shared task specification, using JSON mode when supported.

    The callable accepts `response_format={"type": "json_object"}` when available and
    returns an object with a `.text` attribute. Invalid generations receive a corrective retry.
    """
    cleaned_request = request.strip()
    if not cleaned_request:
        raise ValueError("Enter a one-line request first.")
    if len(cleaned_request) > 500:
        raise ValueError("The coding request must be 500 characters or fewer.")

    base_prompt = SPEC_PROMPT.format(request_json=json.dumps(cleaned_request, ensure_ascii=False))
    prompt = base_prompt
    max_attempts = max(1, min(int(attempts), 3))
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            try:
                reply = call(
                    prompt,
                    system=SPEC_SYSTEM,
                    max_tokens=3500,
                    response_format={"type": "json_object"},
                )
            except TypeError as exc:
                # Compatibility with simple/custom test callables that predate response_format.
                if "response_format" not in str(exc):
                    raise
                reply = call(prompt, system=SPEC_SYSTEM, max_tokens=3500)
            payload = _extract_json(getattr(reply, "text", ""))
            return parse_spec(cleaned_request, payload)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max_attempts:
                prompt = (
                    base_prompt
                    + "\n\nCorrection required: the previous response was empty, invalid JSON, or failed schema validation. "
                    "Return a fresh, complete JSON object with every required key. Do not include Markdown fences, "
                    "analysis, or any text outside the JSON object."
                )
    detail = str(last_error) if last_error else "unknown generation failure"
    raise ValueError(f"Could not build a valid task specification after {max_attempts} attempt(s): {detail}")


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
