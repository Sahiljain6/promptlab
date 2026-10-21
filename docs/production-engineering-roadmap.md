# PromptLab Production Engineering Roadmap — 20 Parts

**Status:** planning document only. No runtime code changes are included in this commit.  
**Target repository:** https://github.com/Sahiljain6/promptlab  
**Implementation rule:** work on one part at a time, review the diff, run the relevant tests, and keep each part small enough to revert safely.

## Scope and guardrails

This roadmap adapts the 19 visible topics in the supplied screenshot and adds **Part 20: Observability** as a closely related production concern. The aim is to make PromptLab more reliable without introducing infrastructure that the current app does not need.

PromptLab is currently a Streamlit research application. The codebase uses SQLite for experiment history and the per-instance usage quota, calls model providers through an OpenAI-compatible client, runs trial work with a bounded thread pool, and has a CI workflow for compile checks, unit/security regression tests, and dependency auditing. Some protections already exist; implementation must start by verifying and strengthening them rather than duplicating them.

**Behavior that must remain unchanged unless a specific part requires a reviewed change:**
- Groq and Gemini remain the primary comparison providers; Ollama remains a last-resort code-generation fallback when both primary providers return API errors for the same technique/trial.
- Provider/task-specification fallback behavior remains explicit and testable. A poor model answer or failing evaluation is not, by itself, permission to silently switch providers.
- Provider API keys and the app access password stay server-side. Never print, display, commit, or persist raw secrets.
- AI-estimate mode must not be described as actual code execution. Docker execution remains opt-in and separately reviewed.
- Keep the existing Streamlit UI and research methodology stable unless a change is necessary and approved for the particular part.
- Do not add Redis, a gateway, a reverse proxy, multiple replicas, or a webhook system merely to check a box. Some topics are conditional architecture decisions, not immediate implementation tasks.

## How we will implement the roadmap

For every part:
1. Inspect the relevant code and existing tests before editing.
2. Write a small change with the scope limited to that part.
3. Add or update focused tests, including failure paths.
4. Run **python -m compileall -q app.py promptlab tests** and **python -m unittest discover -s tests -v**.
5. Review the diff for changed behavior, secrets, user-visible model/provider details, data migrations, and compatibility.
6. Report the exact files changed, tests run, results, remaining limitations, and commit/PR link. Do not claim a test passed unless it was actually run.

A part is considered complete when its acceptance criteria are met **or** the code audit proves it is not applicable to the current single-app deployment and the reason plus future trigger is documented.

---

## Part 1 — Idempotency keys

**Goal:** Prevent accidental duplicate submissions from creating duplicate expensive comparisons or quota consumption, while still allowing users to intentionally run the same benchmark again.

**PromptLab plan**
- Trace the Streamlit submission lifecycle and identify how double-clicks, browser reruns, refreshes, or transient UI errors could start a second run.
- Give each user-initiated run a unique operation ID. Reuse that ID only for retries of the same submission; a new deliberate click must generate a new ID.
- Persist the operation ID and state (reserved, running, completed, failed) if durable deduplication is needed. Add a unique database constraint rather than relying only on an in-memory check.
- Decide how completed results are reloaded for the same operation ID and how stale running records recover after a process crash.
- Tie quota reservation to the same operation so a duplicate request does not reserve two slots. Avoid hashing only the task text: identical prompts may be intentional separate experiments.

**Verification / acceptance**
- Simulate duplicate submissions with the same operation ID and assert only one comparison and one quota reservation occur.
- Prove two fresh IDs for identical benchmark inputs create two valid experiments.
- Test failure and restart recovery without leaking a previous user's session state.

## Part 2 — Rate limiting and quotas

**Goal:** Bound cost and prevent one user or a burst of clicks from exhausting provider quotas.

**Current baseline to verify:** **promptlab/storage.py** contains a rolling-window quota reservation using SQLite and **BEGIN IMMEDIATE**; the UI configures a per-instance run limit. This is useful, but must not be described as a globally shared limit across replicas.

**PromptLab plan**
- Document quota dimensions separately: app-level run quota, per-provider request/token budget, per-session login attempts, and upstream provider limits.
- Test the existing atomic reservation under concurrent calls. Verify failed or interrupted work does not accidentally bypass reservations.
- Keep limit configuration bounded and validate malformed settings safely.
- Choose whether quotas are global or per user/session; the current shared-password gate cannot reliably identify individual people.
- If the app ever runs on multiple instances, move quota state to a shared atomic store before claiming a global limit. Do not bolt on a new database just for a single instance.
- Keep provider-side spending limits enabled where available; app quotas are only one layer.

**Verification / acceptance**
- Concurrent requests cannot exceed the intended quota for a single store.
- Denied requests are rejected before provider calls start.
- UI messaging accurately identifies a per-instance limit when that is the actual scope.

## Part 3 — Reverse proxies

**Goal:** Safely terminate TLS and control incoming traffic if PromptLab is self-hosted behind a proxy.

**Applicability:** Streamlit-hosted deployments generally have managed ingress. This part is conditional, not a reason to add Nginx or another service to the current deployment.

**PromptLab plan**
- First document the actual deployment topology and identify which layer owns TLS, request-size limits, idle timeouts, and health checks.
- If self-hosted, use a maintained reverse proxy with HTTPS, secure forwarded-header handling, bounded body sizes, and conservative upstream/read timeouts.
- Trust forwarded host/protocol/IP headers only from known proxy hops. Do not derive security decisions from arbitrary client-supplied forwarded headers.
- Ensure the proxy's idle timeout and the model-call budget agree so long-running comparisons are not cut off unexpectedly.
- Keep secrets out of proxy logs and avoid logging full prompt bodies.

**Verification / acceptance**
- Confirm redirect-to-HTTPS, correct forwarded scheme/host, error behavior, and timeout alignment in the target deployment.
- If managed hosting already supplies these controls, record the evidence and mark proxy configuration as not applicable for now.

## Part 4 — Connection pooling

**Goal:** Reuse outbound HTTP connections to reduce setup overhead and improve reliability during multi-trial runs.

**Current area to inspect:** **promptlab/provider.py** constructs an OpenAI-compatible client for generation calls. Confirm client lifecycle and whether HTTP connections are being reused across trials.

**PromptLab plan**
- Measure whether client creation or TLS/connect setup meaningfully contributes to latency before changing the design.
- Introduce a small provider-client factory/lifecycle that reuses a correctly configured client for the same provider, endpoint, and credential context.
- Bound HTTP connection counts and keep connect/read/overall request timeouts explicit.
- Avoid cross-contaminating sessions when secrets or endpoints change. Do not key a shared cache using raw credentials if that can expose them through diagnostics.
- Ensure clients are closed on shutdown where supported. Do not share mutable per-request state between concurrent calls.

**Verification / acceptance**
- Unit tests verify the right base URL, model, timeout, retry policy, and credential are selected.
- A concurrency test shows calls can proceed in parallel without corrupting responses.
- Benchmark a representative run before and after; keep the change only if it preserves correctness and offers a measurable or maintainability benefit.

## Part 5 — N+1 queries and database access patterns

**Goal:** Keep history views and experiment storage responsive as the database grows.

**Current baseline:** history is stored in a single SQLite experiments table and read in bounded batches. N+1 behavior has not been established from the repository summary; inspect actual query paths before assuming it exists.

**PromptLab plan**
- Inventory queries in **promptlab/storage.py** and history/export UI code.
- Look for loops that issue one SQL query per experiment, repeated initialization/migrations, repeated full-table reads, and unbounded result lists.
- Use joins or batched queries only if relationships are introduced and measurements justify them.
- Inspect query plans before adding indexes; likely candidates depend on actual filters and ordering such as run ID, provider, or creation time.
- Keep SQL parameterized and preserve backward-compatible schema migration behavior.

**Verification / acceptance**
- Add tests for empty history, many history rows, filters, and ordering.
- Confirm query count does not grow linearly with the number of rows for any summary view.
- Record a baseline query-plan or timing check for a realistically sized history set; avoid brittle wall-clock assertions in ordinary unit tests.

## Part 6 — Caching strategies

**Goal:** Avoid repeating expensive work that is safe to reuse, without invalidating the fairness of research comparisons.

**PromptLab plan**
- Classify data as immutable local data, derived display data, experiment output, or secret/user-specific data.
- Consider Streamlit data/resource caching for immutable preset definitions or expensive deterministic local transformations after profiling.
- Do **not** cache provider generations by default: model responses, temperature, provider versions, and experiment repetition are part of the research behavior.
- If a derived result is cached, include all meaningful inputs in its cache key: prompt/specification, technique, model/provider configuration, relevant settings, and schema/version.
- Keep provider secrets, raw credentials, and private session information out of cached values and cache diagnostics.
- Prefer small, bounded caches with explicit TTLs rather than unbounded in-memory dictionaries.

**Verification / acceptance**
- Repeated rendering of cached immutable data yields the same output.
- Changing a relevant input invalidates the cached result.
- A repeated benchmark still makes real provider calls unless the user explicitly invokes a designed replay feature.

## Part 7 — Cache invalidation

**Goal:** Prevent outdated or cross-session data from appearing after a save, delete, setting change, or deployment update.

**PromptLab plan**
- Implement this only alongside an explicitly approved cache in Part 6; do not build invalidation logic for a cache that does not exist.
- Document each cache's owner, key, TTL, and invalidation events.
- Invalidate history/summary caches after experiment saves or deletion; version cache keys for changes to evaluation logic or schema.
- Ensure per-user/session results are not placed in a shared cache without an isolation key.
- Provide a bounded way to clear derived cached data without deleting persistent experiment history or secrets.

**Verification / acceptance**
- Save, update, and delete operations show fresh results on the next view.
- Changed technique/evaluation settings cannot reuse a stale incompatible result.
- Clearing a cache never clears or corrupts the experiment database.

## Part 8 — Load balancing

**Goal:** Add capacity only when one app process or host is a demonstrated bottleneck.

**Applicability:** This is a scale-out decision, not a change to make in the current Streamlit application by default.

**PromptLab plan**
- Establish measurable traffic, concurrency, latency, memory, and failure-rate thresholds that would justify another instance.
- Before adding replicas, remove process-local assumptions from quota, idempotency, job state, and experiment persistence by moving necessary state to a shared durable system.
- Verify Streamlit session/WebSocket affinity requirements for the chosen hosting topology.
- Make worker concurrency and upstream provider budgets safe in aggregate; four workers per instance becomes four times the worker pool with four instances.
- Add health/readiness checks and a rollback path before changing traffic routing.

**Verification / acceptance**
- A multi-instance test preserves session behavior, quotas, and experiment visibility across instances.
- Aggregate concurrency stays within an explicit provider budget.
- If no current scale signal exists, record the decision to defer rather than introducing load-balancer complexity.

## Part 9 — API gateways

**Goal:** Centrally govern authentication, routing, limits, and API versions if PromptLab later exposes a separate HTTP API.

**Applicability:** The current product is a Streamlit UI that calls model-provider APIs; it does not need a gateway merely to make outbound requests.

**PromptLab plan**
- First define an actual API contract and identify which clients need access independently of the Streamlit UI.
- If an API is introduced, evaluate a gateway against the hosting platform's built-in ingress and authentication. Avoid running two overlapping policy layers.
- Require server-side authentication and authorization, request size/schema limits, quotas, timeouts, safe error mapping, versioning, and auditability.
- Keep provider keys on the server. Client callers must never submit arbitrary upstream credentials or select unrestricted provider endpoints.
- Version endpoints deliberately and make breaking changes explicit.

**Verification / acceptance**
- Unauthorized and over-quota calls are rejected before paid provider usage.
- Input validation, API-version behavior, and safe errors are covered by contract tests.
- If no external API consumer exists, keep this part documented as deferred.

## Part 10 — Timeouts and total run budgets

**Goal:** Bound the time and resource cost of one request, including the full technique/trial workflow.

**Current baseline to verify:** **promptlab/provider.py** configures a 90-second provider timeout. A multi-technique run can contain many individual provider calls, so a per-call timeout is not the same as a total-run deadline.

**PromptLab plan**
- Define separate budgets for connection establishment, a provider response, task-spec generation, a repair round, and the total user-initiated run.
- Ensure retries and repair calls cannot silently exceed the overall budget.
- Give the UI clear running/failed states and safe timeout messaging; never display raw provider diagnostics without redaction.
- Decide how cancelled/expired runs finalize their history records and quota reservations.
- Keep enough headroom for Streamlit host/request limits. Avoid blindly shrinking all provider timeouts because slow valid responses are possible.

**Verification / acceptance**
- A simulated hung provider exits within its configured time budget.
- A run with several slow calls cannot continue indefinitely.
- Timeout errors are distinguishable from invalid credentials, invalid model IDs, and evaluation failures.

## Part 11 — Retry policy

**Goal:** Retry transient failures when safe while avoiding duplicate work, extra cost, and hidden latency.

**Current baseline to verify:** the provider SDK is configured with **max_retries=2**, and task specification generation has its own bounded attempts. These layers must be reviewed together.

**PromptLab plan**
- List retryable conditions: transient connection failures, selected 5xx responses, and 429/rate limits when a retry is appropriate.
- Do not retry permanent 400/401/403 errors or invalid model/configuration errors as if they were transient.
- Avoid stacking independent retry loops without a shared total-attempt and time budget.
- Preserve the provider fallback contract and report which provider/attempt failed without returning secrets or entire raw requests.
- Treat generation and evaluation separately: do not call another model merely because the generated code fails tests unless a specific, tested research policy says to do so.

**Verification / acceptance**
- Tests cover retryable and non-retryable status codes and prove that the maximum attempt count is bounded.
- A successful first attempt is never repeated.
- Fallback behavior for task specification and code generation remains consistent with the README.

## Part 12 — Exponential backoff with jitter

**Goal:** Avoid rapid retry storms during rate limits or provider outages.

**PromptLab plan**
- Inspect the SDK's current retry behavior before adding custom delays; do not layer a second backoff loop on top of the SDK without a clear reason.
- When custom control is needed, use capped exponential backoff with random jitter, a maximum attempt count, and the overall time budget from Part 10.
- Respect a valid Retry-After header when the SDK exposes it.
- Use provider-aware handling for 429 responses and distinguish temporary quota/rate exhaustion from a permanently misconfigured account.
- Keep deterministic clock/random injection in tests so timing behavior can be tested without slow sleeps.

**Verification / acceptance**
- Delay progression is bounded and includes jitter outside deterministic tests.
- The implementation does not retry beyond the configured deadline.
- Unit tests use a fake clock/sleeper and confirm that permanent errors do not back off and retry.

## Part 13 — Circuit breakers

**Goal:** Temporarily stop sending requests to a provider that is repeatedly failing, rather than making every experiment wait for the same outage.

**PromptLab plan**
- Define a small provider health state machine: closed, open, and half-open, with a bounded cool-down period.
- Count only appropriate transient failures. Do not trip the breaker for user input errors, bad prompts, invalid credentials, or failed code evaluations.
- Make fallback interactions explicit so a circuit-open primary provider can follow the existing fallback policy without a hidden change in comparison methodology.
- Decide whether state is process-local for the current single-instance deployment. If scaling later, use a shared store only if cross-instance coordination is required.
- Display a safe and actionable error without leaking provider responses or credentials.

**Verification / acceptance**
- Repeated synthetic 5xx/429 failures open the breaker at the expected threshold.
- After the cool-down, a limited half-open probe can restore normal traffic.
- Successful responses close the breaker; permanent configuration errors are reported, not endlessly retried.

## Part 14 — Race conditions

**Goal:** Ensure concurrent Streamlit sessions and worker threads cannot corrupt quota, run records, or displayed results.

**Current baseline to verify:** usage reservation uses SQLite's immediate transaction; code generation runs provider/technique work concurrently. Those protections do not automatically make every other operation atomic.

**PromptLab plan**
- Inventory shared mutable state in module globals, Streamlit session state, client objects, and SQLite tables.
- Make one run's results belong to its run ID; do not let overlapping runs overwrite another session's last result.
- Add database uniqueness constraints where the data model requires uniqueness, and use transactions for related writes.
- Keep each transaction short and avoid holding database locks while waiting for a model provider.
- Add stress tests for concurrent quota reservations and experiment writes.

**Verification / acceptance**
- Concurrent tests preserve every expected row and never exceed the shared quota.
- Each visible result set maps to the correct run ID and session.
- Repeated or interrupted operations cannot create partially inconsistent records.

## Part 15 — Deadlocks and lock contention

**Goal:** Keep database writes and concurrent provider work from waiting forever or starving other requests.

**Current baseline to verify:** SQLite connections use a bounded connection timeout. The quota path uses **BEGIN IMMEDIATE**; ordinary experiments are stored separately. Review all transaction boundaries before adding locks.

**PromptLab plan**
- Keep transactions short and never wrap model API calls or expensive evaluation in a database transaction.
- Define one lock/transaction order if multiple resources ever need locking.
- Use timeouts for lock acquisition and return a controlled retryable error instead of hanging the UI.
- Avoid adding explicit Python locks unless a demonstrated shared-state race requires them; an unnecessary lock can serialize model calls.
- Record contention timing without logging prompts, full responses, or secrets.

**Verification / acceptance**
- A test with competing quota/database writes completes or returns a bounded error.
- Provider calls do not hold SQLite write locks.
- A deadlock/timeout cannot strand a persistent record forever in a running state.

## Part 16 — Memory leaks and bounded resource use

**Goal:** Keep long sessions and large comparisons from growing memory usage without limit.

**PromptLab plan**
- Profile representative sessions first, including maximum techniques/trials, history browsing, large generated outputs, and provider failures.
- Review Streamlit session state for stale records, retained DataFrames, prompts, generated code, and diagnostics. Preserve only the data needed for user-visible results.
- Keep thread pools and HTTP clients bounded and reusable; ensure temporary files and sandbox resources are cleaned up.
- Limit history query/export sizes and any new caches. Do not keep all raw provider replies indefinitely.
- For Docker execution, verify timeout, output-size, CPU/memory, and cleanup controls independently from UI-side memory work.

**Verification / acceptance**
- Repeated test runs do not exhibit a steadily growing number of live workers, open connections, or retained objects.
- Large-output and timeout tests stay inside declared limits.
- Any cleanup preserves the current run's results and experiment history required by the UI.

## Part 17 — Webhooks

**Goal:** Accept external events securely only if PromptLab gains a real integration that requires incoming callbacks.

**Applicability:** No webhook receiver is required for the current synchronous Streamlit workflow. This is a future integration part, not something to add pre-emptively.

**PromptLab plan**
- Define the event producer, event types, delivery guarantees, retry behavior, and data needed before exposing an endpoint.
- Verify signatures using a secret, compare timestamps within a tolerance, and reject replays with a durable event ID/idempotency constraint.
- Validate content type and payload schema, cap payload size, and return fast acknowledgements before heavier work is queued.
- Keep processing idempotent and avoid allowing events to trigger arbitrary model prompts, code execution, or user-data access.
- Redact payload contents from logs unless a specific field is known to be safe.

**Verification / acceptance**
- Tests reject invalid signatures, expired timestamps, repeated event IDs, malformed payloads, and oversized bodies.
- A duplicate delivery has no duplicate side effects.
- If no defined event producer exists, defer implementation and keep the future trigger documented.

## Part 18 — CORS

**Goal:** Restrict browser-based cross-origin requests if a separate API is exposed.

**Applicability:** The current Streamlit interface is primarily same-origin and does not need a permissive CORS layer by default.

**PromptLab plan**
- Determine the real frontend origin and whether any browser client calls an independent backend directly.
- If there is no separate browser-facing API, do not add CORS middleware.
- If an API is introduced, allowlist exact required origins, methods, and headers; handle preflight requests correctly.
- Never combine wildcard origins with credentialed requests. CORS is not authentication and does not protect direct server-to-server calls.
- Configure CORS in one deliberate layer unless the architecture requires otherwise.

**Verification / acceptance**
- Tests confirm the approved origin succeeds and an unapproved origin is not granted access.
- Credential and preflight behavior match the documented API design.
- If CORS is not applicable, record the rationale instead of adding broad headers.

## Part 19 — Secrets management

**Goal:** Protect model API keys, the application access password, and any future database or webhook credentials.

**Current baseline to verify:** the app reads configuration through Streamlit Secrets/environment variables, uses an access-password gate, compares passwords with **hmac.compare_digest**, and redacts known configured secrets from surfaced errors. This is a useful base, not proof that every secret-leak path is covered.

**PromptLab plan**
- Keep production secrets only in the hosting platform's secret store; use an ignored local .env for development.
- Scan tracked files, example files, test fixtures, exception output, logs, exports, and CI artifacts for accidental credentials.
- Keep example configuration placeholders obviously fake. Never paste live keys in issues or commits.
- Define rotation steps and least-privilege provider keys; remove/revoke a leaked key immediately rather than merely deleting it from the latest commit.
- Centralize secret-safe error/log formatting. Avoid exposing raw response bodies that might echo request details.
- Review session login-attempt limits in the context of the hosting model; per-session throttling is not the same as a global brute-force control.
- Preserve the existing UI promise not to expose internal model IDs if that is an established product requirement.

**Verification / acceptance**
- Automated checks find no known secret patterns in tracked files.
- Tests assert that known test secrets never appear in returned error strings or logs.
- Missing or malformed secrets fail closed with clear setup guidance and no provider call.

## Part 20 — Observability: structured logs, metrics, and traces

**Goal:** Make failures and latency diagnosable without collecting sensitive prompts or model output unnecessarily.

**PromptLab plan**
- Use a run/correlation ID consistently across task-spec generation, each provider attempt, each technique/trial, quota reservation, and persistence. The pipeline currently assigns a run ID to result records; verify when it is created and make it available to earlier steps without changing experiment semantics.
- Emit structured events for start/end, duration, provider, technique key, trial, retry count, fallback reason, timeout/error category, token usage when provided, quota rejection, and persistence failures.
- Never log API keys, the access password, raw prompts, hidden tests, full generated code, or raw provider output by default. Diagnostics should be opt-in and carefully redacted.
- Separate operational telemetry from research records: research history is for experiment analysis; logs/metrics are for health and troubleshooting.
- Track request counts, success/error rate by provider, latency percentiles, retries, fallback rate, quota denials, and database-lock/timeout frequency.
- Add a lightweight health/diagnostic view only if it can be protected from public access and does not reveal internal model identifiers contrary to the UI requirement.
- Choose thresholds and retention that fit the hosting platform; avoid paid monitoring dependencies until the need is proven.

**Verification / acceptance**
- A single synthetic run can be followed end-to-end with one correlation ID.
- A forced provider failure is diagnosable by error category and timing without exposing secrets or full user content.
- Telemetry works when a provider omits token usage and does not treat an AI-estimated evaluation as a real execution result.

---

## Recommended execution order

The screenshot numbering is preserved above for traceability. To reduce risk and avoid building infrastructure prematurely, implement in these dependency-aware waves:

1. **Correctness and cost protection:** Parts 1–2 (idempotency and rate limits).
2. **Predictable provider behavior:** Parts 10–13 (timeouts, retry policy, backoff, circuit breakers).
3. **Safe diagnosis and configuration:** Parts 19–20 (secrets and observability).
4. **Concurrency and storage:** Parts 14–15, then Parts 4–5 (race conditions, deadlocks, client reuse, database query patterns).
5. **Data reuse and resource limits:** Parts 6–7 and 16 (caching, invalidation, memory/resource bounds).
6. **Deployment architecture decisions:** Parts 3, 8–9, 18 (reverse proxy, load balancing, gateway, CORS)—only when the deployment actually needs them.
7. **External integration:** Part 17 (webhooks)—only after a concrete producer and use case exist.

After each wave, re-run the existing CI commands and confirm no regression in provider fallback semantics, research fairness, secret handling, history exports, or the Streamlit UI. Each part should be implemented and reviewed separately; do not bundle all 20 runtime changes into one commit.
