# PromptLab — Dual-Model Code Generation Research

PromptLab is a Streamlit application for the research project **“A Comparative Study of Prompt Engineering Techniques for Improving Code Generation Accuracy in LLMs.”** It sends each selected prompt-engineering technique to **Groq and Gemini automatically**, tests the generated Python implementations, scores every model/technique pair, and shows the best-ranked response along with all generated code outputs.

## What it does

1. Enter a one-line coding request or choose a preset benchmark.
2. Groq creates a shared function specification, visible examples, and hidden test cases for a one-line request so both coding models face the same benchmark.
3. PromptLab sends the same selected techniques to both **Groq** and **Gemini**; there is no provider or model selector in the interface.
4. Compare correctness, solved rate, generation latency, token usage, and execution time where available.
5. Rank every provider/technique pair using a configurable weighted score.
6. Display every generated solution and detailed test outcomes, plus the best-ranked prompt/code and example/custom output.
7. Save experiment history and download CSV/JSON results.

The ten prompt techniques are zero-shot, few-shot, persona-based, function signature + docstring, structured specification, private planning, chain-of-thought, structured chain-of-thought, decomposition, and self-repair.

## Requirements

- Python 3.10 or newer (Python 3.11 or 3.12 recommended).
- Both a Groq API key and a Gemini API key.
- Optional Docker Desktop for stronger code-execution isolation.

## Configure API keys

### Streamlit Cloud

Open your Streamlit app dashboard → **Settings → Secrets**. Store both keys there:

```toml
GROQ_API_KEY = "your-groq-api-key"
GEMINI_API_KEY = "your-gemini-api-key"
```

The keys are read on the server and are not rendered as input fields in the interface. Never commit real API keys to GitHub. If the app is public, visitors can still trigger API usage and costs, so restrict access or add authentication and rate limits.

### Local Windows setup

1. Clone or download the repository and open PowerShell in the project folder.
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

4. Copy `.env.example` to `.env` and set both keys:

   ```powershell
   Copy-Item .env.example .env
   ```

5. Start the app:

   ```powershell
   python -m streamlit run app.py
   ```

6. Open the localhost URL shown in the terminal, typically http://localhost:8501.

## Backend model defaults

The app fixes the model IDs in backend settings, so visitors cannot select a different model:
- Groq: `openai/gpt-oss-20b`
- Gemini: `gemini-3.8-flash`

Optional backend overrides can be set as Streamlit Secrets or local environment variables: `GROQ_MODEL`, `GEMINI_MODEL`, and `GROQ_TEST_MODEL`. For a comparable experiment, keep the IDs stable across trials.

Gemini uses Google's OpenAI-compatible endpoint `https://generativelanguage.googleapis.com/v1beta/openai/`; the API key is the Gemini key. See [Google's OpenAI compatibility guide](https://ai.google.dev/gemini-api/docs/openai).

## Test evaluation modes

- **AI estimate via Groq (default):** asks Groq to predict likely outcomes by inspecting each generated solution. It does not execute Python, so label these results as AI estimates rather than verified correctness.
- **Auto:** uses Docker if available; otherwise it uses a local Python subprocess.
- **Local Python:** executes the code in a subprocess with time/resource limits and blocks some imports as a deterrent. This is not a security boundary.
- **Docker sandbox:** runs the code in a Docker container with network disabled, resource limits and a read-only work directory.

For research-grade correctness, prefer actual execution inside Docker and validate generated test expectations. Do not run untrusted generated code in a public service using an ordinary subprocess without additional isolation.

## Scoring and metrics

The default score is:

`score = 100 × (0.70 × accuracy + 0.10 × speed + 0.10 × token efficiency + 0.10 × execution efficiency)`

The sidebar offers Accuracy first, Balanced, and Speed & cost first weight presets. Accuracy excludes test cases that every model/technique failed, which are flagged as potentially suspect. If a provider does not report token counts, PromptLab estimates tokens using characters divided by four.

Metrics include adjusted test accuracy, solved rate, generation latency, token usage, execution time where measured, and the composite score.

## Run unit tests

```powershell
python -m unittest discover -s tests -v
```

## Project structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI, dual-model comparison, charts, results, and exports |
| `promptlab/prompts.py` | Ten prompt templates and code extraction |
| `promptlab/tasks.py` | Request-to-specification flow and preset tasks |
| `promptlab/pipeline.py` | Concurrent model/technique runs and self-repair |
| `promptlab/provider.py` | OpenAI-compatible clients for Groq, Gemini, and optional custom endpoints |
| `promptlab/sandbox.py` | Docker, local, and Groq AI-estimate evaluation modes |
| `promptlab/scoring.py` | Suspect-test filtering, ranking, composite scores, best-response selection |
| `promptlab/storage.py` | SQLite experiment history and schema migration |
| `tests/` | Prompt, pipeline, and execution tests |

## Research cautions

Use the same task definition and tests for both models, repeat trials, compare more than one task family, and retain raw records. A single model can make mistakes when creating specifications or judging code. AI-estimated results are not execution results; do not present them as verified pass rates.
