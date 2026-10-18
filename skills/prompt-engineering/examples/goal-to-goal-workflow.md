# Goal-to-goal workflow: example

This example shows how the skill should move from intake to a mapped route and a copy-ready master prompt. The scenario is illustrative.

## First response: get the two anchors

**User:** I want an AI shopping website.

**Agent:** What is your goal, and where are you starting from right now? Tell me what you want to achieve, what you already have or have completed, and any blockers. Plain language is fine.

## Follow-up: fill only important gaps

**User:** I want a website where users describe what they want to buy and it compares products and live deals. I already have a React frontend and a FastAPI backend. Catalog search works but live deals aren't reliable. I want to improve it without breaking login or the existing chat.

**Agent:** I understand the target and current state. One detail that changes the plan: which live shopping provider is configured today, and should the site keep working when that provider is missing or unavailable?

**User:** SerpApi is the primary provider; DuckDuckGo should be the fallback. Keep existing auth and chat working.

If the current repository is available, inspect it before assuming which modules implement these functions. If it is not accessible, state that limitation and proceed from the supplied description.

## Goal and starting point

- **Goal:** a shopping site that returns relevant product recommendations and live deal information, with reliable provider fallback.
- **Starting point:** existing React + FastAPI application, working catalog search, existing login and chat; live deals are unreliable.
- **Must preserve:** login, current chat behavior, catalog functionality, React/FastAPI architecture.
- **Known provider behavior desired:** SerpApi primary; DuckDuckGo fallback when the key is absent or the provider fails.
- **Unknown until inspected:** current live-search implementation, response schemas, caching, and relevant tests.

## Route map: current state → goal

| Phase | Work | Deliverable | Checkpoint |
|---|---|---|---|
| 1. Inspect and baseline | Inspect frontend, API routes, provider integration, environment configuration, and tests. Reproduce the current failure if possible. | Short architecture summary and a documented current-state baseline. | Identify existing behavior and tests before changing code. |
| 2. Specify the response contract | Define the normalized deal fields and how empty results, provider errors, missing keys, and stale cached results are represented. | Explicit response contract and fallback decision table. | Confirm the contract does not break current frontend expectations. |
| 3. Repair the primary provider | Correct configuration, request handling, parsing, error handling, and caching for SerpApi. Keep secrets server-side. | Reliable structured live listings when SerpApi succeeds. | Add tests using mocked provider responses; never require a real secret in tests. |
| 4. Add and verify fallback | Ensure DuckDuckGo is attempted only under the intended fallback conditions and the API returns a predictable response if both providers fail. | Consistent behavior across primary, fallback, and total-failure cases. | Test no-key, successful primary, primary error, fallback error, and empty-result paths. |
| 5. Integrate the UI | Confirm the frontend renders structured listings and gracefully handles unavailable prices, images, and links. | Clear loading, empty, and error states without disturbing auth/chat. | Run relevant frontend checks and backend tests. |
| 6. Regression and handoff | Run available tests, compare affected behavior against the baseline, document required configuration, and summarize limits. | Tested changes and a concise handoff report. | Existing login, chat, and catalog checks remain passing; report any unverified areas. |

## Copy-ready master prompt

> **Mission:** Diagnose and repair the live shopping search workflow in the existing React + FastAPI application so product discovery can combine catalog results with current retailer listings.
>
> **Starting point:** Catalog search currently works. Live deal results are unreliable. Login, existing chat, and catalog behavior must be preserved. SerpApi is the intended primary live-shopping provider, and DuckDuckGo is the fallback when the SerpApi key is missing or the provider fails.
>
> **Before changing code:** Inspect the repository, map the actual routes and service modules, review environment variables and response schemas, and identify relevant tests. Report what you found and do not invent files or architecture details.
>
> **Implementation roadmap:**
> 1. Establish the current behavior and reproduce known failures where possible.
> 2. Define a stable normalized response schema for live deals, including missing optional fields and provider-failure cases.
> 3. Repair SerpApi request/configuration/parsing behavior while keeping credentials server-side.
> 4. Implement or verify DuckDuckGo fallback and predictable behavior when both providers fail.
> 5. Confirm the frontend handles successful results, empty results, missing images/prices, loading, and errors.
> 6. Run relevant unit, regression, and build checks; update tests and configuration docs.
>
> **Constraints:** Keep the existing React + FastAPI architecture. Avoid unrelated refactoring. Preserve authentication, chat, and catalog behavior. Never expose secrets or embed them in frontend code. Use mocked API responses in automated tests; do not require production credentials to run the test suite.
>
> **Checkpoints:** Before broad changes, summarize affected modules and proposed approach. After each major phase, report changed files, tests/checks run and results, and any blockers. Ask before destructive or irreversible operations.
>
> **Definition of done:** Primary provider success, missing-key fallback, provider-error fallback, empty results, and total provider failure are handled predictably; the frontend consumes the agreed response schema; existing protected features continue to work; relevant tests pass or failures are clearly documented; configuration and limitations are documented honestly.
>
> **Final handoff:** Summarize root cause, files changed, provider behavior, tests actually run, deployment/configuration steps, and remaining risks. Do not claim anything was verified unless it was.

## What this example demonstrates

The skill asks for the goal and current state first, asks a targeted follow-up only where an answer changes the implementation, maps phases to deliverables and checks, and embeds the resulting route into a self-contained prompt. It does not assume repository details before inspection.
