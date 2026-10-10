from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTechnique:
    key: str
    name: str
    description: str


TECHNIQUES = [
    PromptTechnique("zero_shot", "Zero-shot", "Direct task instruction; baseline."),
    PromptTechnique("few_shot", "Few-shot", "Includes a small worked example to demonstrate the expected style."),
    PromptTechnique("persona", "Persona-based", "Frames the model as an experienced Python engineer."),
    PromptTechnique("structured", "Structured specification", "Organizes constraints, edge cases, and output requirements."),
    PromptTechnique("plan_code", "Stepwise planning", "Asks the model to plan privately, then return code only."),
]

FEW_SHOT_EXAMPLE = '''Example of the expected output style:
Task: Write a function is_even(n) that returns True when n is even and False otherwise.
Output:
def is_even(n):
    return n % 2 == 0
'''


def build_prompt(technique_key: str, task_name: str, task_description: str, function_name: str, function_signature: str) -> str:
    common = f"""Programming task: {task_name}

Specification:
{task_description}

Required function name: {function_name}
Required function signature:
{function_signature}

Language: Python 3
Return a single Python module containing the required function. Do not include Markdown fences, explanations, test code, or example output. Follow the specification exactly."""

    if technique_key == "zero_shot":
        technique_instructions = "Implement the requested function directly from the specification."
    elif technique_key == "few_shot":
        technique_instructions = ("Use the following small example as a demonstration of concise function implementation style. "
                                  "Do not copy its logic unless it applies to the requested task.\n\n" + FEW_SHOT_EXAMPLE)
    elif technique_key == "persona":
        technique_instructions = ("Act as a careful senior Python engineer. Prefer correct, readable, maintainable code; "
                                  "consider boundary conditions and use standard Python conventions. Return only the implementation.")
    elif technique_key == "structured":
        technique_instructions = ("Use this implementation checklist: (1) satisfy every requirement, (2) handle boundary cases, "
                                  "(3) use the requested function name and signature, (4) avoid unnecessary dependencies and side effects, "
                                  "(5) ensure the result can be imported as a Python module. Return only code.")
    elif technique_key == "plan_code":
        technique_instructions = ("Before writing the answer, privately identify the algorithm, important edge cases, and likely failure modes. "
                                  "Do not reveal your private reasoning or a plan. Return only the final Python implementation.")
    else:
        raise ValueError(f"Unknown prompting technique: {technique_key}")

    return f"{technique_instructions}\n\n{common}"


def clean_generated_code(text: str) -> str:
    """Remove common Markdown wrappers while preserving the generated Python module."""
    import re
    import textwrap

    output = (text or "").strip()
    fenced = re.search(r"```(?:python|py)?\s*\n(.*?)```", output, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        output = fenced.group(1).strip()
    else:
        lines = output.splitlines()
        start = None
        code_starters = ("def ", "async def ", "class ", "import ", "from ", "@", "#", '\"\"\"', "\"\"\"", "if __name__")
        for index, line in enumerate(lines):
            if line.lstrip().startswith(code_starters):
                start = index
                break
        if start is not None:
            output = "\n".join(lines[start:]).strip()
    return textwrap.dedent(output).strip() + "\n"
