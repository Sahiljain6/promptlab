# Provider routing and fallback behavior

PromptLab keeps provider selection on the server. Users choose prompt techniques and experiment settings, not provider model IDs.

## Code-generation comparisons

The normal comparison uses two primary providers:

1. **Groq** generates one candidate for each selected technique and trial.
2. **Gemini** generates the corresponding candidate using the same task specification and tests.
3. **Ollama Cloud** is a last-resort backup. It is called for a technique/trial only when both primary providers return an API error or an empty response.

A candidate that is returned successfully but fails evaluation does **not** trigger Ollama. This distinction keeps a weak model result visible in the comparison rather than silently replacing it with a backup result.

When Ollama is used, its result is labelled as a fallback and is not treated as a routine third comparison provider.

## One-line task specification

For a user-written one-line request, PromptLab first creates a shared task specification and test suite. The configured order is:

1. Groq
2. Gemini, if Groq cannot produce a valid specification
3. Ollama Cloud, if neither primary provider can produce a valid specification and Ollama is configured

The first valid specification is shared by both primary code-generation providers. This prevents the compared models from receiving different task definitions or test cases.

Preset benchmark tasks use the built-in specification and do not need a provider-generated task specification.

## Gemini rate-limit rotation

The primary Gemini model is configured with `GEMINI_MODEL`. You can optionally supply additional permitted model IDs in `GEMINI_FALLBACK_MODELS`, separated by commas.

PromptLab tries the configured Gemini model IDs in order **only when the current Gemini request appears to be rate-limited** (HTTP 429 or an error message indicating a rate limit, quota, or `resource_exhausted`). Other errors are returned instead of silently switching models.

Only use model IDs enabled for the Gemini API project associated with `GEMINI_API_KEY`. Model rotation does not guarantee that another model has available quota.

## Environment variables

Set these values in local `.env` for development or in Streamlit App Settings → Secrets for a hosted deployment. Never commit real credentials.

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Required API key for the primary Groq provider |
| `GEMINI_API_KEY` | Required API key for the primary Gemini provider |
| `OLLAMA_API_KEY` | Optional API key for the Ollama Cloud backup |
| `PROMPTLAB_ACCESS_PASSWORD` | Required password gate for the hosted app |
| `GROQ_MODEL` | Groq model ID; defaults to `openai/gpt-oss-20b` |
| `GEMINI_MODEL` | Primary Gemini model ID; defaults to `gemini-3.8-flash` |
| `GEMINI_FALLBACK_MODELS` | Optional comma-separated Gemini model IDs to try after a rate-limit response |
| `OLLAMA_MODEL` | Ollama backup model ID; defaults to `gpt-oss:20b-cloud` |
| `OLLAMA_BASE_URL` | Ollama-compatible endpoint; defaults to `https://ollama.com/v1` |
| `GROQ_TEST_MODEL` | Optional Groq model override for AI-estimate evaluation |
| `PROMPTLAB_MAX_RUNS_PER_HOUR` | Per-instance rolling-hour comparison limit; defaults to `6` |
| `PROMPTLAB_ENABLE_DOCKER_EXECUTION` | Docker execution opt-in; defaults to `false` |

See [`.env.example`](../.env.example) for a ready-to-copy template with placeholder values.

For local Ollama only, the app permits an HTTP endpoint when the hostname is loopback (for example, `http://localhost:11434/v1`). Hosted or remote Ollama endpoints must use HTTPS.

## Troubleshooting checklist

- **The app remains locked:** set a non-empty `PROMPTLAB_ACCESS_PASSWORD` in the deployment's secrets.
- **The comparison button is disabled:** configure both `GROQ_API_KEY` and `GEMINI_API_KEY`.
- **Ollama backup is unavailable:** check `OLLAMA_API_KEY`, `OLLAMA_BASE_URL`, and whether the configured model is enabled for the account. The backup is optional; primary comparisons can still run.
- **Gemini reaches quota:** configure one or more eligible IDs in `GEMINI_FALLBACK_MODELS`. Rotation is attempted for rate-limit/quota errors only.
- **A generated answer fails tests:** this is an evaluation result, not an API failure, so it does not by itself trigger the Ollama backup.
- **Actual code execution is unavailable:** AI-estimate mode does not execute generated code. Docker execution appears only when Docker is available and the app owner explicitly enables it.

For security, keep provider credentials and the access password in deployment secrets. Do not place real keys in source files, screenshots, issue reports, or experiment exports.
