# PromptLab — Dual-Model Code Generation Research

PromptLab is a Streamlit app for the project **“A Comparative Study of Prompt Engineering Techniques for Improving Code Generation Accuracy in LLMs.”** It automatically sends the same task and selected prompt techniques to Groq and Gemini, evaluates the solutions, ranks every model/technique pair, and shows the highest-ranked response with the other outputs.

## What it does

1. Enter a one-line coding request or select a preset task.
2. Groq creates a shared function specification, visible examples, and hidden test cases for a one-line request. The API call enables JSON mode; malformed or incomplete responses receive a corrective retry, and the app can fall back to Gemini if Groq still cannot produce a valid specification.
3. PromptLab sends each selected technique to both Groq and Gemini automatically. There is no provider/model selector in the UI.
4. Compare estimated/observed correctness, solved rate, latency, token usage, and execution time where available.
5. Rank all model/technique combinations with configurable score weights.
6. View every generated code solution, the best-ranked prompt/code, and example/custom outputs.
7. Save experiment history and export CSV/JSON.

The ten prompt techniques are zero-shot, few-shot, persona-based, function signature + docstring, structured specification, private planning, chain-of-thought, structured chain-of-thought, decomposition, and self-repair.

## Required configuration

### Streamlit Community Cloud

In your app dashboard, open **Settings → Secrets** and add:

    GROQ_API_KEY = "your-groq-api-key"
    GEMINI_API_KEY = "your-gemini-api-key"
    PROMPTLAB_ACCESS_PASSWORD = "replace-with-a-long-random-password"

The app is locked until PROMPTLAB_ACCESS_PASSWORD is configured. Visitors must enter that password before the app can use your provider keys. Do not share this password publicly. For stronger protection, make the Streamlit app private/restricted as well.

Optional backend defaults:

    GROQ_MODEL = "openai/gpt-oss-20b"
    GEMINI_MODEL = "gemini-3.8-flash"
    GROQ_TEST_MODEL = "openai/gpt-oss-20b"
    PROMPTLAB_MAX_RUNS_PER_HOUR = "6"
    PROMPTLAB_ENABLE_DOCKER_EXECUTION = "false"

Model IDs and provider endpoints are configured on the server; visitors cannot change them in the interface. If the default Gemini model is not available on your account, set GEMINI_MODEL to a model your Gemini account can access.

Gemini uses Google's OpenAI-compatible endpoint, fixed server-side at `https://generativelanguage.googleapis.com/v1beta/openai/`, with `GEMINI_API_KEY`. See [Google's Gemini OpenAI compatibility guide](https://ai.google.dev/gemini-api/docs/openai).

### Local Windows setup

1. Clone/download the repository and open PowerShell in the project folder.
2. Create and activate a virtual environment:

       py -m venv .venv
       .venv\Scripts\Activate.ps1

3. Install dependencies:

       python -m pip install --upgrade pip
       pip install -r requirements.txt

4. Copy .env.example to .env. Add real keys and choose a long random value for PROMPTLAB_ACCESS_PASSWORD. Never commit .env.

       Copy-Item .env.example .env

5. Start the app:

       python -m streamlit run app.py

6. Open the local URL shown in the terminal, typically http://localhost:8501.

## Evaluation and execution safety

- **AI estimate (default):** Groq predicts likely outcomes by inspecting generated code and test cases. This is not actual Python execution, so results must be labeled as estimates.
- **Docker execution:** Only appears when Docker is available and the app owner explicitly sets PROMPTLAB_ENABLE_DOCKER_EXECUTION=true. The runner disables network access, uses a read-only work mount, a non-root UID, dropped Linux capabilities, resource limits, and timeouts.
- **Host-local Python subprocess:** Not available in the web UI. The underlying developer-only mode requires PROMPTLAB_ALLOW_UNSAFE_LOCAL_EXECUTOR=true and should not be enabled for a public app.
- **Auto mode:** Does not fall back to host-local Python when Docker is unavailable.

Generated code is untrusted. AI estimate is the recommended mode for a hosted demo. If actual execution is needed, use an isolated Docker environment and review its security settings before enabling the feature.

## Security changes

The current version adds these protective measures:

- App access password required; the app fails closed if PROMPTLAB_ACCESS_PASSWORD is missing.
- API keys and endpoint settings are loaded from Streamlit Secrets or local environment variables, not shown as input fields.
- Provider errors are redacted before being displayed.
- A SQLite rolling-hour quota limits the number of new comparisons per running app instance (default six, configurable up to thirty).
- Request length, trial count, and custom example argument count are capped.
- Host-local subprocess execution is hidden from the UI and requires an explicit developer-only environment flag.
- Docker auto mode does not fall back to host execution.
- Docker has a tighter read-only/non-root/resource-limited configuration and temporary file permissions are set so the non-root runner can read the files.

These are defense-in-depth controls, not a substitute for platform-level access restriction, provider-side usage budgets, monitoring, and a security review. A shared app password can be forwarded; keep the Streamlit app restricted to intended users. A per-instance quota may reset if the app restarts or uses another instance.

## Scoring

The default composite score is:

    score = 100 × (0.70 × accuracy + 0.10 × speed + 0.10 × token efficiency + 0.10 × execution efficiency)

The app supports Accuracy first, Balanced, and Speed & cost first weighting. A test case failed by every variant may be flagged as potentially suspect and excluded from adjusted accuracy. Review such tests; do not automatically assume every all-model failure means the expected value is wrong.

## Run unit tests

    python -m unittest discover -s tests -v

## Custom-task troubleshooting

If a one-line request fails while creating the shared task specification:

- PromptLab requests JSON mode from the provider API instead of relying on prompt wording alone.
- It extracts a valid JSON object even when a compatible provider adds brief leading prose, validates the function signature and test data, and retries an invalid response once.
- If Groq still fails, it tries Gemini to build the shared specification. Both coding models still receive that same specification and hidden test suite.
- Requests are limited to 500 characters. Simplify an unusually complicated request or use the **Preset benchmark task** option to check whether provider credentials and model access work.
- Check that `GROQ_MODEL` and `GEMINI_MODEL` are available to the configured accounts. The app will show the provider and error type if both task-specification attempts fail.
- JSON mode improves syntactic validity but can still fail on edge cases, and it does not guarantee that every generated expected value is mathematically correct. Verify generated test expectations before treating accuracy as research-grade.

The Groq model configured by default supports JSON mode and structured outputs; Google's Gemini OpenAI-compatible endpoint also supports JSON output mode:
- [Groq structured outputs](https://console.groq.com/docs/structured-outputs)
- [Google's Gemini OpenAI compatibility guide](https://ai.google.dev/gemini-api/docs/openai)

## Research notes

- Use the same request, test cases, temperature, and model versions for comparisons.
- Run several tasks and repeated trials before drawing conclusions.
- AI-estimated outcomes must not be reported as verified pass rates.
- Generated tests can have incorrect expected values; validate them independently for research-grade claims. Automatic suspect-test filtering uses actual executed outcomes only; AI estimates are not evidence that a hidden test is wrong.
- API failures and unavailable evaluations are tracked as missing/invalid trials instead of being treated as incorrect code or receiving a positive composite score. The results table shows total and valid trial counts.
- Token counts may be estimated when a provider does not report usage.

## Repository structure

- app.py — Streamlit interface, access gate, paired-model comparison, charts and exports.
- promptlab/prompts.py — prompt templates and code extraction.
- promptlab/tasks.py — one-line request specification and preset tasks.
- promptlab/pipeline.py — concurrent technique/model runs and self-repair.
- promptlab/provider.py — Groq and Gemini OpenAI-compatible provider calls.
- promptlab/sandbox.py — Docker, developer-only local runner, and Groq AI-estimate evaluator.
- promptlab/scoring.py — suspect-test filtering, per-pair summary, scoring and best-response selection.
- promptlab/storage.py — SQLite history, migration, and usage quota.
- tests/ — prompt/pipeline/executor tests.
