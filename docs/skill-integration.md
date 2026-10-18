# Integrating the Prompt Engineering Skill

The PromptLab skill is a portable folder of Markdown instructions and supporting resources. It is not an API service and does not retrain a model.

## 1. Load it using the public repository link

For an AI assistant that can access public GitHub repositories, give it this URL:

https://github.com/Sahiljain6/promptlab

Ask it to read and apply:

- `skills/prompt-engineering/SKILL.md`
- `skills/prompt-engineering/references/goal-to-goal-planning.md`
- `skills/prompt-engineering/references/technique-selection.md`
- `skills/prompt-engineering/examples/goal-to-goal-workflow.md`
- `skills/prompt-engineering/examples/transformations.md`

The core instruction tells the agent to establish the user's goal and starting point for substantial tasks, then map phases, deliverables, dependencies, checkpoints, risks, and the definition of done before generating a copy-ready master prompt.

A ready-to-paste activation prompt is available in the [skill README](../skills/prompt-engineering/README.md).

A repository link alone cannot force every AI product to fetch every file. The product needs browsing, a GitHub connector, or another way to retrieve repository content. The agent should report files it actually accessed.

## 2. If the agent cannot open GitHub

Provide the contents of the raw core instructions:

https://raw.githubusercontent.com/Sahiljain6/promptlab/main/skills/prompt-engineering/SKILL.md

For goal mapping, also provide the raw [planning guide](https://raw.githubusercontent.com/Sahiljain6/promptlab/main/skills/prompt-engineering/references/goal-to-goal-planning.md) and [example workflow](https://raw.githubusercontent.com/Sahiljain6/promptlab/main/skills/prompt-engineering/examples/goal-to-goal-workflow.md).

## 3. Install for persistent use

If the target agent supports skills, install or register the full `skills/prompt-engineering/` directory using that platform's documented method. Keep the reference and example files alongside `SKILL.md`. Agent platforms may have different packaging, permissions, and installation behavior; follow their documentation.

The skill's intended opening question for a new substantial task is:

> What is your goal, and where are you starting from right now? Tell me what you want to achieve, what you already have or have completed, and any blockers. Plain language is fine.

The agent should use existing conversation context so it does not ask for information the user has already given. For a simple task, it may proceed without an unnecessary interview.

## 4. Use it with the PromptLab research app

The components are related but separate:

- **Portable skill:** clarifies goals, maps tasks, and creates prompts. It does not require a model-provider key.
- **Research app:** runs code-generation comparisons and uses API credentials configured by the app owner.

Loading the skill does not execute code, run benchmarks, grant repository access, or permanently change model weights.

## Trust and limitations

- Review instruction files before installing them.
- The skill does not override higher-priority instructions or platform safety controls.
- Do not paste secrets or confidential material unnecessarily.
- Ask for confirmation before destructive, costly, external, or irreversible actions.
- An improved prompt or roadmap does not guarantee that the downstream agent's result will be correct.

## Evaluation

Compare changes against a fixed set of tasks. Rate whether the skill correctly captures the goal and starting point, maps realistic phases and dependencies, preserves constraints, provides testable checkpoints, generates a usable master prompt, and handles uncertainty safely. Save the scenarios and scoring rationale; do not claim improvement without measured results.
