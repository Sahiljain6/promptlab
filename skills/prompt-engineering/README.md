# Prompt Engineering Skill

A reusable, model-independent AI skill that helps users clarify a goal, describe their starting point, map a route from current state to desired outcome, and generate a specific master prompt for the next AI agent.

## Fastest way to use it

Give an AI assistant that can access public GitHub repositories this link:

~~~text
https://github.com/Sahiljain6/promptlab
~~~

Then ask it to follow the skill, not merely summarize it:

~~~text
Read the PromptLab repository at https://github.com/Sahiljain6/promptlab. Apply skills/prompt-engineering/SKILL.md together with its goal-to-goal planning guide, technique-selection guide, and examples.

For my next substantial task, begin by making sure you understand my goal and my starting point. Ask me what I want to achieve and what I already have, have completed, or am blocked by, unless I already provided that context. Clarify only important gaps. Then map the route from current state to goal with phases, deliverables, dependencies, checkpoints, risks, and a definition of done. Generate a specific, self-contained master prompt that I can give to an AI agent. Do not merely polish my wording. Preserve all constraints, state assumptions, and do not invent progress or test results. For a small, self-contained task, keep the process lightweight.
~~~

## What should happen after loading

For a new substantial task, the assistant should start with a short conversational intake:

> **What is your goal, and where are you starting from right now?** Tell me what you want to achieve, what you already have or have completed, and any blockers. Plain language is fine.

After enough context is collected, it should return:
1. A short summary of the goal and starting point.
2. A route map from current state to goal.
3. A copy-ready master prompt containing that route, constraints, checkpoints, and acceptance criteria.
4. Important assumptions or open questions, if any.

The skill uses information already provided and avoids repeating questions. It does not force a lengthy interview for a simple task.

## Included files

- **SKILL.md** — default behavior, goal-first intake, roadmap mapping, master-prompt generation, quality and safety rules.
- **references/goal-to-goal-planning.md** — how to bridge current state to the desired goal.
- **references/technique-selection.md** — guidance for choosing prompt techniques and reviewing quality.
- **examples/goal-to-goal-workflow.md** — illustrative intake, roadmap, and master-prompt example.
- **examples/transformations.md** — before-and-after examples for software, research, data analysis, and writing.

## Important limitation

The agent needs browsing, a GitHub connector, or another method to access the public files. If it cannot fetch the repository, provide the raw [SKILL.md](https://raw.githubusercontent.com/Sahiljain6/promptlab/main/skills/prompt-engineering/SKILL.md) contents. Reading a skill guides a session; it does not retrain model weights. For repeated use, install the skill through the target platform's supported mechanism.

## Principles

- Understand both the desired outcome and the actual starting point.
- Map concrete phases, deliverables, dependencies, checkpoints, and success criteria.
- Preserve user intent and explicit constraints.
- Ask only useful clarification questions.
- Distinguish facts from assumptions and never invent verification.
- Keep task maps and prompts proportional to task complexity.

## Contributing

Issues and pull requests are welcome. Prefer reproducible examples: include the user's initial goal and starting point, the generated roadmap and prompt, and the criteria used to judge whether it was useful. Do not submit secrets, private user data, or proprietary prompts without permission.

Check the repository root for current licensing information before redistributing this material.
