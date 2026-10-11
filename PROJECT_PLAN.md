# PromptLab implementation roadmap

## Version 1 — working foundation
- [x] Browser-based Streamlit app
- [x] Real model API connector via OpenAI-compatible chat completions
- [x] Five prompt strategies
- [x] Four preset tasks and editable custom tests
- [x] Isolated Docker test runner
- [x] SQLite history, charts, CSV export

## Version 2 — research readiness
- [ ] Import task datasets from JSON/CSV and add more complexity levels
- [ ] Batch-run selected tasks × all techniques × multiple models
- [x] Repeat trials and run IDs (fixed seeds / resumable batches still open)
- [ ] Add confidence intervals and paired significance tests
- [x] Syntax-error, runtime-error, timeout, blocked and correctness statuses
- [ ] Add a paper-ready results export and run metadata manifest

- [x] One-line request to spec/tests, 10 techniques, real execution with timing, best-prompt ranking
- [x] JSON-mode task-spec generation, schema validation, corrective retries, and cross-provider fallback
- [x] Keep preset visible examples separate from hidden scoring tests
- [ ] Import datasets (HumanEval/MBPP), multi-model batch runs, confidence intervals and paired significance tests

## Version 3 — web deployment
- [ ] Separate frontend from isolated runner service
- [ ] Use remote disposable containers or a hardened code-execution service
- [x] Add app-password gate, per-instance run quota, secret management, redacted errors, and Docker execution opt-in
- [ ] Add platform-level identity/authentication, provider-side budgets, monitoring, and a hardened remote execution service
- [ ] Add PostgreSQL if multiple users need shared history

Security status: the hosted UI defaults to Groq AI-estimate mode and does not expose host-local subprocess execution. The Docker runner is admin-opt-in and hardened with basic resource/isolation settings, but this is not a full penetration test or a guarantee of perfect isolation. Keep the Streamlit app private/restricted and use provider-side quotas; prefer a separately managed hardened runner before allowing arbitrary generated code execution for untrusted users.
