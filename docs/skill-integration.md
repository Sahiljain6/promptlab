# Integrating the Prompt Engineering Skill

The PromptLab skill is a directory of Markdown instructions and supporting resources. It does not call a model provider by itself.

## 1. Load it by pasting the repository link

For an AI assistant that can browse public GitHub repositories, provide this URL:

https://github.com/Sahiljain6/promptlab

Ask the assistant to read the following files and apply them as instructions for the current session:

- skills/prompt-engineering/SKILL.md
- skills/prompt-engineering/references/technique-selection.md
- skills/prompt-engineering/examples/transformations.md

A ready-to-paste instruction is available in the [root README](../README.md#use-the-skill-by-pasting-the-github-link).

The assistant should confirm what it actually read instead of claiming access it did not have. A repository link alone cannot force every AI product to fetch a repository; the product must have browsing, a GitHub connector, or another way to access the files.

## 2. Use the raw core file as a fallback

If the assistant cannot browse the repository, paste the contents of the raw core instructions:

https://raw.githubusercontent.com/Sahiljain6/promptlab/main/skills/prompt-engineering/SKILL.md

If supported, also supply the technique guide and examples. A direct raw-file URL can be easier for some tools to fetch than the repository's HTML page.

## 3. Install for repeated use

For an agent that supports Agent Skills, use its documented skill installation/loading mechanism and supply the full skills/prompt-engineering/ directory. Keep SKILL.md and its reference/example files together.

The expected SKILL.md layout follows the open Agent Skills pattern of YAML frontmatter with a skill name and description followed by Markdown instructions. See the [Agent Skills specification](https://agentskills.io/specification) and your platform's own documentation for exact installation paths and supported behavior.

Not every agent supports the same import mechanism. Some will only follow the skill during the current conversation, while others can load it from a project or persistent skills directory.

## 4. Use it with PromptLab's research app

The Streamlit app and the portable skill serve related but distinct purposes:

- **Portable skill:** provides prompt-improvement instructions. No API key or Streamlit runtime is needed to read the files.
- **Research app:** runs code-generation comparisons and uses provider API credentials configured by the app owner.

Loading the skill does not run experiments, train a model, or permanently change model weights.

## Compatibility, trust, and limitations

- Check the target agent's documentation before installing skills or granting repository access.
- Review the instruction files before trusting or installing them; repository content is still third-party input.
- The skill does not override higher-priority instructions or platform safety controls.
- Do not provide secrets or confidential material unnecessarily.
- An improved prompt does not guarantee the downstream model's answer is correct.

## Suggested evaluation for contributors

Compare skill revisions against a fixed set of prompts covering software, research, writing, data analysis, and planning. Rate intent preservation, constraint coverage, clarity, output specificity, verification, safety, and conciseness. Keep the test set and scoring rationale so reviewers can reproduce results. Do not report benchmark improvements without actual measurements.
