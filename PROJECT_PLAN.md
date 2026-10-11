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
- [ ] Import datasets (HumanEval/MBPP), multi-model batch runs, confidence intervals and paired significance tests

## Version 3 — web deployment
- [ ] Separate frontend from isolated runner service
- [ ] Use remote disposable containers or a hardened code-execution service
- [ ] Add authentication, rate limiting, quotas, and secret management
- [ ] Add PostgreSQL if multiple users need shared history

Do not deploy the local Docker execution feature directly to an untrusted public environment.
