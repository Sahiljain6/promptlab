# Prompt Engineering Skill

A reusable, model-independent set of instructions for improving prompts across software development, research, writing, data analysis, planning, and AI-agent workflows.

## Fastest way to use it

Start by pasting the public repository link into an AI assistant that can access GitHub:

~~~text
https://github.com/Sahiljain6/promptlab
~~~

Then ask it to read and apply these files:

- skills/prompt-engineering/SKILL.md
- skills/prompt-engineering/references/technique-selection.md
- skills/prompt-engineering/examples/transformations.md

Use this instruction with the link:

~~~text
Read the PromptLab repository above. Load skills/prompt-engineering/SKILL.md and its referenced technique-selection guide and examples. Do not merely summarize them: follow the skill for this conversation and use it to improve any prompt I give you. Preserve my goal and explicit constraints, choose techniques appropriate to the task, make important assumptions visible, and return a copy-ready improved prompt. Tell me honestly if you cannot access a file.
~~~

The assistant must be able to access the repository or fetch web pages for the link-based method to work. If it cannot fetch files, open the [raw SKILL.md](https://raw.githubusercontent.com/Sahiljain6/promptlab/main/skills/prompt-engineering/SKILL.md) and paste its contents into the conversation.

Loading the skill gives the assistant instructions to follow in the current conversation or session; it does not retrain the underlying model. For continued use, install the folder using the target platform's supported skill mechanism. See the [integration guide](../../docs/skill-integration.md).

## Included files

- **SKILL.md** — the core workflow and quality/safety rules.
- **references/technique-selection.md** — technique selection guidance and an evaluation rubric.
- **examples/transformations.md** — illustrative before-and-after transformations.

## Principles

- Preserve the user's intent and every explicit constraint.
- Use only techniques that address a real task need.
- Specify expected outputs and useful acceptance criteria.
- Distinguish facts from assumptions and never invent verification.
- Request concise rationales or validation summaries, not hidden chain-of-thought.
- Keep prompts as short as possible while remaining complete.

## Contributing

Issues and pull requests are welcome. Prefer reproducible examples: include the original prompt, rewritten prompt, reason for the change, and criteria used to judge it. Do not submit secrets, private user data, or proprietary prompts without permission.

Check the repository's root README for the current licensing status before redistributing this material.
