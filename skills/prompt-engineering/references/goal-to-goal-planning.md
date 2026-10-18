# Goal-to-goal planning guide

Use this guide when a request involves a project, multi-step outcome, troubleshooting effort, implementation, research plan, or other work where the user needs to get from a current state to a desired state.

## Begin with two anchors

Ask naturally:

> What is your goal, and where are you starting from right now? Tell me what you want to achieve, what you already have or have completed, and any blockers. Plain language is fine.

Use information already available in the conversation; never ask users to repeat themselves. If the user only provided one anchor, ask for the other when it materially affects the route. For a tiny, self-contained edit, the supplied text may be enough and a roadmap may be unnecessary.

## Turn answers into a state transition

A useful task map shows the path from current state to end state.

| Element | Question answered |
|---|---|
| Starting point | What exists now? What works, is complete, or is blocked? |
| Goal state | What should be true when the work succeeds? |
| Gap | What is missing between now and the goal? |
| Phases | What sequence of changes or decisions bridges the gap? |
| Deliverables | What tangible outcome comes out of each phase? |
| Dependencies | What must be true or completed before the next phase? |
| Checkpoints | How will progress and correctness be checked? |
| Risks | What could fail, regress, require approval, or need an assumption? |
| Definition of done | What observable criteria prove completion? |
| Next action | What is the smallest useful first step? |

## Keep the intake lightweight

Explore relevant constraints such as platform, existing stack, budget, deadline, tools/access, required format, dependencies, and excluded work. Do not ask for every item every time. Ask at most a couple of high-value follow-ups before presenting a draft route. Use explicit assumptions for low-risk unknowns; ask before decisions that change the goal or carry significant cost, safety, or irreversible impact.

## Recommended task-map format

For substantial work:

| Phase | Focus / actions | Deliverable | Dependency or validation |
|---|---|---|---|
| 1. Inspect / baseline | Establish the actual current state | Baseline summary | Verify what is present before modifying it |
| 2. Specify | Clarify the required behavior and contract | Requirements / acceptance checklist | Resolve high-impact ambiguity |
| 3. Implement / execute | Make scoped changes in dependency order | Working milestone | Focused tests or evidence |
| 4. Integrate | Connect the pieces and preserve existing behavior | Integrated result | Regression checks |
| 5. Verify and hand off | Test against the goal and document limitations | Final deliverable and report | Definition-of-done checklist |

Adapt these phases; they are not mandatory boilerplate. Research tasks may need source collection and synthesis; writing tasks may need outline, draft, review; personal planning may need milestones and decisions rather than code tests.

## Generate a self-contained master prompt

The prompt must carry over the goal, starting point, constraints, task map, milestone deliverables, checkpoints, definition of done, and instructions for honest reporting. Do not depend on the next agent seeing the original chat. Specify whether the downstream agent should only plan, prepare a prompt, or actually execute. Default to plan-first for substantial requests unless the user explicitly asks for execution.

## Avoid common failures

- Do not list generic phases without tying them to the user's actual state.
- Do not assume a codebase or tools were inspected if they were not.
- Do not convert unknowns into facts.
- Do not build a huge roadmap for a simple task.
- Do not confuse making a prompt more detailed with making it more effective.
- Include checkpoints that verify progress, not only a final test.
- Report blockers and deviations instead of pretending the route completed as planned.
