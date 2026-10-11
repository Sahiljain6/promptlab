from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTechnique:
    key: str
    name: str
    description: str
    reasoning: bool = False      # model is allowed to write reasoning before the final code block
    multi_call: bool = False     # technique uses more than one LLM call (self-repair)


TECHNIQUES = [
    PromptTechnique("zero_shot", "Zero-shot", "Raw one-line request only; the baseline."),
    PromptTechnique("few_shot", "Few-shot", "Adds worked input/output examples for this task."),
    PromptTechnique("persona", "Persona-based", "Frames the model as an experienced Python engineer."),
    PromptTechnique("function_signature", "Function signature + docstring", "Gives exact typed signature and asks for a docstring."),
    PromptTechnique("structured", "Structured specification", "Constraint checklist plus the expanded specification."),
    PromptTechnique("plan_code", "Private planning", "Plan silently, return code only."),
    PromptTechnique("cot", "Chain-of-Thought", "Reason step by step, then give the final code.", reasoning=True),
    PromptTechnique("structured_cot", "Structured CoT", "Reason over inputs, outputs, edge cases, algorithm, then code.", reasoning=True),
    PromptTechnique("decomposition", "Decomposition", "Plan helper functions first, then implement them.", reasoning=True),
    PromptTechnique("self_repair", "Self-repair", "Generate, run on the visible examples, repair using error feedback.", multi_call=True),
]
TECHNIQUE_BY_KEY = {t.key: t for t in TECHNIQUES}

SYSTEM_CODE_ONLY = ("You are a code-generation engine. Output only valid Python source code for the requested function. "
                    "Do not output Markdown fences, explanations, test cases, or hidden reasoning.")
SYSTEM_REASONING = ("You are an expert Python engineer. Think through the problem briefly in plain text, then finish with the "
                    "complete final solution in exactly one ```python code block. Do not include test code.")

GENERIC_EXAMPLE = '''Example of the expected output style:
Task: Write a function is_even(n) that returns True when n is even and False otherwise.
Output:
def is_even(n):
    return n % 2 == 0
'''


def system_for(technique_key: str) -> str:
    return SYSTEM_REASONING if TECHNIQUE_BY_KEY[technique_key].reasoning else SYSTEM_CODE_ONLY


def max_tokens_for(technique_key: str) -> int:
    return 3000 if TECHNIQUE_BY_KEY[technique_key].reasoning else 1500


def format_examples(function_name: str, examples: list[dict]) -> str:
    lines = []
    for ex in examples:
        args = ", ".join(json.dumps(a, ensure_ascii=False) for a in ex.get("args", []))
        lines.append(f"{function_name}({args}) -> {json.dumps(ex.get('expected'), ensure_ascii=False)}")
    return "\n".join(lines)


def build_prompt(technique_key: str, task_name: str, task_description: str, function_name: str,
                 function_signature: str, examples: list[dict] | None = None, request: str = "") -> str:
    """Turn one task into the prompt for a given technique.

    `request` is the user's raw one-line request (used verbatim by the zero-shot baseline).
    `task_description` is the expanded specification used by the richer techniques.
    """
    request = (request or task_description).strip()
    base = f"Task: {request}\nThe function must be named `{function_name}`.\nLanguage: Python 3."
    spec = f"Detailed specification:\n{task_description}"
    sig = f"Required function signature:\n{function_signature}"
    code_only = "Return only the Python code, no Markdown fences and no explanations."
    final_block = "Finish with the complete final solution in a single ```python code block."

    if technique_key == "zero_shot":
        return f"{base}\n\n{code_only}"
    if technique_key == "few_shot":
        shown = format_examples(function_name, examples or [])
        extra = f"Input/output examples for this function:\n{shown}\n\n" if shown else ""
        return (f"{base}\n\n{extra}Use this small example only as a style demonstration, not as logic to copy.\n"
                f"{GENERIC_EXAMPLE}\n{code_only}")
    if technique_key == "persona":
        return ("You are a careful senior Python engineer with ten years of experience writing correct, readable, "
                f"maintainable code who always considers boundary conditions.\n\n{base}\n\n{code_only}")
    if technique_key == "function_signature":
        return (f"{base}\n\n{sig}\nInclude a docstring that describes the arguments, return value and edge cases.\n\n{code_only}")
    if technique_key == "structured":
        return (f"{base}\n\n{spec}\n\n{sig}\n\nImplementation checklist: (1) satisfy every requirement, (2) handle boundary cases, "
                "(3) use the requested function name and signature, (4) avoid unnecessary dependencies and side effects, "
                f"(5) ensure the result can be imported as a Python module.\n\n{code_only}")
    if technique_key == "plan_code":
        return (f"{base}\n\n{spec}\n\n{sig}\n\nBefore answering, privately identify the algorithm, important edge cases and likely "
                f"failure modes. Do not reveal your reasoning. {code_only}")
    if technique_key == "cot":
        return (f"{base}\n\nThink step by step: restate the problem, work out the logic, then write the solution. {final_block}")
    if technique_key == "structured_cot":
        return (f"{base}\n\n{spec}\n\n{sig}\n\nReason using exactly this structure before coding:\n"
                "1. Inputs and outputs (types and ranges)\n2. Edge cases and invalid inputs\n3. Algorithm in plain steps\n"
                f"4. Time and space complexity\nThen: {final_block}")
    if technique_key == "decomposition":
        return (f"{base}\n\n{sig}\n\nFirst write a short numbered plan that breaks the problem into small helper functions. "
                f"Then implement the helpers and `{function_name}` as the entry point. {final_block}")
    if technique_key == "self_repair":
        # First round only; build_repair_prompt() is used for later rounds.
        return f"{base}\n\n{sig}\n\n{code_only}"
    raise ValueError(f"Unknown prompting technique: {technique_key}")


def build_repair_prompt(original_prompt: str, previous_code: str, feedback: str) -> str:
    return (f"{original_prompt}\n\nYour previous attempt:\n```python\n{previous_code.strip()}\n```\n\n"
            f"When run on the visible examples it produced these problems:\n{feedback}\n\n"
            "Fix the code so every example passes. Return only the complete corrected Python code, no explanations.")


def clean_generated_code(text: str, function_name: str | None = None) -> str:
    """Extract the Python module from a model reply (handles fences, reasoning text, truncation)."""
    output = (text or "").strip()
    blocks = [b.strip() for b in re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", output, flags=re.IGNORECASE | re.DOTALL)]
    if blocks:
        chosen = None
        if function_name:
            for block in reversed(blocks):
                if re.search(rf"def\s+{re.escape(function_name)}\s*\(", block):
                    chosen = block
                    break
        output = chosen or blocks[0]
    else:
        lines = output.splitlines()
        start = None
        code_starters = ("def ", "async def ", "class ", "import ", "from ", "@", "#", '"""', "if __name__")
        for index, line in enumerate(lines):
            if line.lstrip().startswith(code_starters):
                start = index
                break
        if start is not None:
            output = "\n".join(lines[start:]).strip()
    return textwrap.dedent(output).strip() + "\n"
