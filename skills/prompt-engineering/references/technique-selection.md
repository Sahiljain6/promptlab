# Technique selection guide

Choose techniques based on the failure mode in the original prompt. This is practical guidance, not a claim that any technique always improves performance.

| Diagnosed problem | Technique | Application | Avoid when |
|---|---|---|---|
| Vague goal | Goal clarification | State the outcome and observable success conditions | The goal is already clear |
| Missing context | Context framing | Add relevant audience, environment, inputs, and known facts | Context would have to be invented |
| Many requirements | Constraint checklist | List hard requirements, exclusions, and priorities | A simple instruction is enough |
| Unpredictable output | Output contract | Specify headings, schema, code interface, or file format | Format is immaterial |
| Specialized repeated task | Few-shot examples | Add correct, representative input/output pairs | Examples may bias the task or add overhead |
| Large task | Decomposition | Divide into stages, deliverables, dependencies, and integration checks | The task is small |
| Code or calculations | Test-driven prompting | Add edge cases, tests, invariants, and validation criteria | Tests cannot yet be meaningfully specified |
| Factual research | Source requirements | Define preferred sources, citations, dates, and uncertainty handling | The task is purely creative |
| Subjective deliverable | Evaluation rubric | Define quality dimensions and priorities | A rubric would be artificial |
| Low-risk ambiguity | Explicit assumptions | Proceed with a reasonable, visible assumption | The assumption changes the goal |
| High-impact ambiguity | Clarifying question | Ask the smallest question that materially changes the result | Context already answers it |
| Tool-using task | Tool/action boundaries | Specify permitted actions, checkpoints, and confirmations | No tools or external actions are involved |
| Checkable output | Verification pass | Request relevant tests, consistency checks, or evidence | The model cannot perform the check; state the limitation |
| Iterative work | Revision criteria | Define review criteria and a final verification pass | One pass is sufficient |

## Goal-to-goal planning and decomposition

For a substantial task, gather the user's **desired goal** and **starting point / current state** before constructing the final prompt. Bridge the two with a concrete route map:
- Summarize what exists and what has already been done.
- Describe observable end-state criteria.
- Identify the gap between current and target states.
- Break the work into ordered phases with tangible deliverables.
- Record dependencies and important decisions.
- Add verification checkpoints, likely risks, and a definition of done.
- Specify the next smallest useful action.

Ask only high-value questions, use known conversation context, and state reasonable low-risk assumptions. Do not invent progress, tools, repository structure, or results. Keep a simple task simple; use detailed phase maps for work with meaningful dependencies.

See [the full planning guide](goal-to-goal-planning.md) and [goal-to-goal example](../examples/goal-to-goal-workflow.md).

## Adaptable prompt skeleton

Use only relevant sections:
1. Task: concrete outcome.
2. Context: facts needed to do the task.
3. Requirements: hard constraints, exclusions, and priorities.
4. Inputs: source material, data, code, or examples.
5. Process: steps or tools when they add reliability.
6. Output: exact format and required contents.
7. Acceptance criteria: how completion will be assessed.
8. Uncertainty and verification: how to handle missing facts, tests, citations, and limitations.

## Avoid technique inflation

- A persona is not a substitute for task details.
- “Think step by step” is not a substitute for a verifiable output contract.
- More words do not automatically improve a prompt.
- Few-shot examples must be correct and representative.
- Do not request hidden chain-of-thought; request a concise rationale, assumptions, or verification summary.
- Remove redundant instructions and resolve contradictory priorities.
- Do not promise accuracy improvements without measurement.

## Lightweight review rubric

Score each dimension from 0 to 2: 0 = missing/poor, 1 = partial, 2 = clear/strong.
- Goal and intent preservation
- Relevant context
- Constraint coverage
- Output specificity
- Acceptance criteria and verification
- Assumption and uncertainty handling
- Safety and instruction hierarchy
- Conciseness and usability

Maximum score: 16. Use this rubric to compare drafts consistently, not as proof that a model's final answer is correct. Record examples and scoring rationale when using it for research.
