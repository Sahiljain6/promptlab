# PromptLab — Code Generation Accuracy Research

PromptLab is a Streamlit web application for the project **“A Comparative Study of Prompt Engineering Techniques for Improving Code Generation Accuracy in LLMs.”** It calls a real LLM API, compares five prompt templates, tests generated Python functions in a Docker container, and stores experiment results in SQLite for analysis and CSV export.

## Features

- Streamlit browser interface
- Real inference using Groq, OpenAI, or a custom OpenAI-compatible endpoint
- Five techniques: zero-shot, few-shot, persona-based, structured specification, and stepwise planning
- Preset tasks plus custom task and test-case editor
- Docker-based test execution with network disabled, resource limits, read-only work mount, non-root user, and timeout
- Correctness, test pass rate, model latency, and token usage when reported by the provider
- SQLite history, aggregate charts, and CSV export

## Requirements

- Python 3.10 or newer (Python 3.11 or 3.12 recommended)
- Docker Desktop installed and running for test execution
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

You can also enter an API key in the app sidebar for the current session. Keys are not stored in the experiment database.

## Provider configuration

The default provider is Groq, using the OpenAI-compatible endpoint. The default model ID is `openai/gpt-oss-20b`; model availability may change, so use an active model ID from your provider dashboard. Configure `GROQ_API_KEY` in `.env` or paste it into the sidebar. OpenAI and other compatible endpoints are also supported.

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

Generated code is untrusted. The evaluator runs code in Docker with no network, a read-only mounted work directory, a non-root user, CPU/memory/PID limits, and a timeout. This reduces risk but is not a guarantee of perfect isolation. Keep Docker updated and run the app locally. Do not expose this development executor as a public service without a hardened remote sandbox, authentication, rate limiting, secret management, and a security review.

## Research limitations

The included preset suite is a starter test set, not a standardized benchmark. Expand task diversity, run repeated trials, preserve raw records, and compare multiple model IDs before making broad claims about prompting techniques.
