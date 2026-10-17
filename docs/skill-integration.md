# Integrating the Prompt Engineering Skill

The skill is model-provider independent and can be reused in compatible agent environments.

## Option 1: Agent supports skill directories

Use the repository's skills/prompt-engineering/ directory with the skill-loading mechanism documented by your agent. Keep the directory structure intact so the core instructions can refer to the technique guide and examples.

## Option 2: Agent supports a single instruction file

Provide skills/prompt-engineering/SKILL.md as the agent's instructions. If the agent cannot follow links to local files, copy relevant guidance from references/technique-selection.md into its instruction or knowledge store.

## Option 3: Chat interface without persistent skills

Paste the contents of SKILL.md into the conversation, then provide the prompt you want improved. Some interfaces have context limits or do not retain instructions across chats.

## Option 4: Use alongside the PromptLab app

The existing Streamlit app evaluates prompt-engineering techniques for code-generation research. This portable skill is a separate instruction artifact that can improve prompts for many task types without calling Groq, Ollama Cloud, or Gemini. Prompt rewriting is not the same as model-output validation.

## Compatibility and limitations

- No model provider or API key is required to read or reuse the skill.
- Agents differ in supported skill formats and file-loading behavior; check the target agent's documentation.
- An agent following instructions cannot guarantee a correct output. Use tests, source checks, or domain review where needed.
- Do not paste secrets or confidential information into prompts unless necessary and authorized.
- The skill does not override the target platform's higher-priority instructions or safety controls.

## Suggested evaluation for contributors

Compare old and new skill versions against a fixed set of prompts covering software development, research, writing, data analysis, and planning. Rate intent preservation, constraint coverage, clarity, output specificity, verification, safety, and conciseness. Save prompts and scoring rationale so reviewers can reproduce the comparison. Do not report benchmark improvements without actual results.
