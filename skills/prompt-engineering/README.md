# Prompt Engineering Skill

A portable, model-independent skill that helps compatible AI agents transform vague or ordinary requests into clear, actionable prompts with appropriate context, constraints, output formats, and acceptance criteria.

## Quick start

1. Open [SKILL.md](SKILL.md).
2. Use the folder with an agent's documented skill-loading mechanism, or provide SKILL.md as the agent's instructions.
3. Ask the agent to improve a prompt, for example: “Improve this prompt for a coding agent: Build a login page.”
4. Check that the rewritten prompt preserves your goal and constraints before using it.

The skill itself requires no API key, specific model, Python runtime, or PromptLab web app. Compatibility depends on the target agent's ability to load instruction files. See [integration notes](../../docs/skill-integration.md).

## Included files

- SKILL.md — core instructions and quality/safety checks.
- references/technique-selection.md — technique selection guide and lightweight evaluation rubric.
- examples/transformations.md — before/after examples for software, research, data analysis, and writing.

## Principles

- Preserve the user's intent and explicit constraints.
- Choose techniques based on the task instead of making prompts longer by default.
- Ask a clarifying question only when a missing detail materially changes the result.
- Request verifiable outputs and honest uncertainty, not hidden chain-of-thought.
- Never claim that a prompt or generated answer is correct without evidence.

## Contributing

Issues and pull requests are welcome. Share reproducible examples, explain the failure mode, and include a before/after prompt plus evaluation rationale where possible. Do not submit secrets, private user data, or proprietary prompts without permission.

The skill is distributed under the license specified at the repository root. If redistributing it independently, retain applicable license and attribution notices.
