# PromptLab — Code Generation Accuracy Research

PromptLab is a Streamlit web application for the project **“A Comparative Study of Prompt Engineering Techniques for Improving Code Generation Accuracy in LLMs.”** It calls a real LLM API, compares five prompt templates, evaluates generated Python functions, and stores experiment results in SQLite for analysis and CSV export.

## Features

- Streamlit browser interface
- Real inference using Groq, OpenAI, or a custom OpenAI-compatible endpoint
- Five techniques: zero-shot, few-shot, persona-based, structured specification, and stepwise planning
- Preset tasks plus custom task and test-case editor
- Cloud AI review through Hugging Face Router (predicts likely test outcomes by code inspection; it does not execute Python)
- Optional local Docker test execution with network disabled, resource limits, read-only work mount, non-root user, and timeout
- Correctness, test pass rate, model latency, and token usage when reported by the provider
- SQLite history, aggregate charts, and CSV export

## Requirements

- Python 3.10 or newer (Python 3.11 or 3.12 recommended)
- For cloud AI review: a Hugging Face access token with access to the configured Router model. For actual local test execution: Docker Desktop installed and running
- API key for the selected model provider

## Windows setup

1. Download or clone this repository and open a terminal in the project folder.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and add your API key. Never commit `.env` to GitHub.

   ```powershell
   Copy-Item .env.example .env
   ```

5. Start Docker Desktop and pull the sandbox image:

   ```powershell
   docker pull python:3.12-slim
   docker info
   ```

6. Start the application:

   ```powershell
   python -m streamlit run app.py
   ```

7. Open the local URL printed in the terminal, usually http://localhost:8501.

Credentials are loaded from server-side Streamlit Secrets or local environment variables; the app does not render API-key input fields and keys are not stored in the experiment database. Configure `HF_TOKEN` for cloud AI review; without it, the app attempts actual test execution through local Docker.

## Provider configuration

The default code-generation provider is Groq, using the OpenAI-compatible endpoint. The default model ID is `openai/gpt-oss-20b`; model availability may change, so use an active model ID from your provider dashboard. Configure `GROQ_API_KEY` in local `.env` or in Streamlit Cloud app Settings → Secrets. OpenAI and other compatible endpoints are also supported. Use `OPENAI_API_KEY` for OpenAI, or `PROMPTLAB_API_KEY`, `PROMPTLAB_BASE_URL`, and optionally `PROMPTLAB_MODEL` for a compatible code-generation endpoint.

Cloud test review uses the Hugging Face Router with `HF_TOKEN` and optional `HF_TEST_MODEL` (default `zai-org/GLM-5.3:novita`). Add those values to Streamlit Cloud Settings → Secrets or your local `.env` file. The Hugging Face model predicts test outcomes by inspecting the code; it does not execute Python. These outcomes must be labeled and analyzed as AI estimates, not ground-truth runtime results.

## Run unit tests

```powershell
python -m unittest discover -s tests -v
```

## Run an experiment

1. Choose a preset task or define a custom task.
2. Confirm the function signature and expected test cases.
3. Keep model, temperature, task, and test cases the same when comparing prompting techniques.
4. Select techniques and click **Run experiment**.
5. Inspect the generated code and actual test outcomes.
6. Use History & analysis to compare saved runs and export a CSV.

Ground-truth tests are used by the evaluator and are not sent to the model.

## Metrics

- **Task success rate:** percentage of generated solutions passing every test.
- **Test pass rate:** passed cases divided by executed cases.
- **Latency:** API response time, excluding test execution.
- **Token usage:** prompt/completion counts when returned by the provider.

API errors and runs not tested because Docker is unavailable should not be treated as verified code failures.

## Safety notes

Generated code is untrusted. Cloud AI review calls the Hugging Face Router and predicts outcomes from source code; it is not a secure execution sandbox and cannot verify actual runtime behavior. Actual local execution uses Docker with no network, a read-only mounted work directory, a non-root user, CPU/memory/PID limits, and a timeout. No sandbox guarantees perfect isolation. Never commit keys to GitHub. On Streamlit Cloud, store credentials in the app's Settings → Secrets rather than source code. Server-side secrets are not displayed to visitors, but visitors who can use a public app may still trigger API calls and costs; restrict access or add authentication and rate limiting before using your own paid provider key in a public deployment. Do not expose a self-hosted executor publicly without authentication, rate limiting, secret management, and a security review.

## Research limitations

The included preset suite is a starter test set, not a standardized benchmark. Expand task diversity, run repeated trials, preserve raw records, and compare multiple model IDs before making broad claims about prompting techniques.
