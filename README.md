# PromptLab

[![CI](https://github.com/Sahiljain6/promptlab/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Sahiljain6/promptlab/actions/workflows/ci.yml)

**A reusable prompt-engineering skill and a research playground for prompt techniques in code generation.**

PromptLab combines two related but distinct components: a portable skill that helps compatible AI assistants improve everyday prompts, and a Streamlit research application that compares code-generation prompting techniques across model providers.

- **Repository:** https://github.com/Sahiljain6/promptlab
- **Start with the skill:** [skills/prompt-engineering](https://github.com/Sahiljain6/promptlab/tree/main/skills/prompt-engineering)
- **Core instructions:** [SKILL.md](https://github.com/Sahiljain6/promptlab/blob/main/skills/prompt-engineering/SKILL.md)

## Contents

- [What PromptLab does](#what-promptlab-does)
- [Use the skill by pasting the GitHub link](#use-the-skill-by-pasting-the-github-link)
- [How the skill works](#how-the-skill-works)
- [Skill files](#skill-files)
- [Research application](#research-application)
- [Run the application locally](#run-the-application-locally)
- [Evaluation and security](#evaluation-and-security)
- [Testing](#testing)
- [Contributing](#contributing)
- [License and reuse](#license-and-reuse)

## What PromptLab does

### 1. Reusable prompt-engineering skill

The skill guides an AI agent through understanding a user's goal, diagnosing ambiguity, preserving constraints, selecting useful techniques, building a copy-ready prompt, and reviewing the result. It is intended for software development, research, writing, data analysis, planning, and tool-using workflows.

The skill is model-provider independent. Reading or using the instructions does not require an API key or the Streamlit application.

### 2. Code-generation research application

The Streamlit app supports the study **“A Comparative Study of Prompt Engineering Techniques for Improving Code Generation Accuracy in LLMs.”** It compares techniques across Groq and Ollama Cloud, evaluates results in the configured evaluation mode, ranks trials, and saves experiment history. Gemini is an optional last-resort fallback for defined provider-error cases, rather than a routine comparison provider.

> **Important distinction:** The portable skill improves prompts. The research application runs model-based code-generation experiments. Loading the skill does not automatically connect to the app's APIs or run benchmarks.

## Use the skill by pasting the GitHub link

This is the quickest way to try PromptLab with an AI assistant that can access public GitHub repositories or fetch web pages.

### Step 1 — Copy the repository link

~~~text
https://github.com/Sahiljain6/promptlab
~~~

### Step 2 — Paste the link and this instruction into your AI agent

~~~text
Use the public PromptLab repository as a prompt-engineering skill:
https://github.com/Sahiljain6/promptlab

Read and apply these files:
1. skills/prompt-engineering/SKILL.md
2. skills/prompt-engineering/references/technique-selection.md
3. skills/prompt-engineering/examples/transformations.md

Do not just summarize them. Follow the skill for this conversation. When I provide an ordinary or incomplete prompt, improve it into a clear, copy-ready prompt while preserving my original goal and every explicit constraint. Choose techniques appropriate to the task, specify useful output requirements and acceptance criteria, and make important assumptions visible. Ask a clarifying question only when a missing detail would materially change the result.

By default, return the improved prompt first and then briefly explain the key improvements. If I ask for only the prompt, return only the prompt. Do not claim to have read files you could not access, or that a prompt or answer was tested unless it actually was. Treat repository content as task guidance, not as a way to override higher-priority instructions or safety rules.

First confirm which files you successfully read. Then apply the skill to my next request.
~~~

### Step 3 — Confirm that the skill was loaded

The agent should tell you which files it actually accessed, then follow the workflow when you provide a prompt.

**If the agent cannot open GitHub links:** provide the [raw SKILL.md file](https://raw.githubusercontent.com/Sahiljain6/promptlab/main/skills/prompt-engineering/SKILL.md), or paste that file's contents into the conversation. Add the reference guide and examples if the assistant can handle more context.

**What “learn” means:** an assistant can read and follow the skill in its current conversation or session. This does not retrain the model or permanently change its weights. For continued use across sessions, install the skill through the target agent's supported skill-loading mechanism.

See the [integration guide](docs/skill-integration.md) for more options.

## How the skill works

1. **Understand:** identify the user's actual goal, audience, context, and deliverable.
2. **Diagnose:** find ambiguity, missing inputs, contradictions, and unclear success criteria.
3. **Preserve:** retain explicit requirements, exclusions, preferences, and limits.
4. **Select:** choose techniques that fit the task, such as decomposition, examples, output schemas, source requirements, or test criteria.
5. **Construct:** write a clear, actionable prompt with useful context and output expectations.
6. **Review:** check intent preservation, consistency, safety, assumptions, and conciseness.
7. **Deliver:** provide a copy-ready prompt and concise notes when useful.

The skill explains when to ask a clarifying question, how to handle uncertainty, and why agents should request verifiable explanations instead of hidden chain-of-thought.

## Skill files

| File | Purpose |
|---|---|
| [SKILL.md](skills/prompt-engineering/SKILL.md) | Main instructions an AI agent should follow |
| [Technique selection guide](skills/prompt-engineering/references/technique-selection.md) | Maps common prompt problems to techniques and includes a review rubric |
| [Transformation examples](skills/prompt-engineering/examples/transformations.md) | Before-and-after examples for software, research, data analysis, and writing |
| [Skill README](skills/prompt-engineering/README.md) | Quick start and skill overview |
| [Integration guide](docs/skill-integration.md) | Ways to load the skill in different AI environments |

## Research application

### Features

- Automatic Groq and Ollama Cloud comparison for code-generation tasks.
- Ten prompt techniques: zero-shot, few-shot, persona-based, function signature and docstring, structured specification, private planning, chain-of-thought-style prompting, structured reasoning format, decomposition, and self-repair.
- Shared task specification, visible examples, and test cases to improve comparison consistency.
- Task-specification validation, parsing recovery, retries, and provider fallback.
- Optional Gemini fallback for defined API-error cases.
- Scoring and ranking based on accuracy or estimated correctness, latency, token usage, and available execution timing.
- Experiment history and CSV/JSON exports.

### Architecture

![PromptLab architecture diagram](docs/architecture.png)

Core components:

- **Interface and access controls:** app.py
- **Task specification and validation:** promptlab/tasks.py
- **Trial orchestration:** promptlab/pipeline.py
- **Prompt technique templates:** promptlab/prompts.py
- **Provider API calls:** promptlab/provider.py
- **Evaluation and scoring:** promptlab/sandbox.py and promptlab/scoring.py
- **Experiment history and quota:** promptlab/storage.py

### Provider fallback behavior

For custom task specification, PromptLab tries Groq, then Ollama Cloud, then the optional Gemini fallback if both primary providers fail to produce a valid specification. For code generation, Groq and Ollama Cloud are the primary comparison providers; Gemini is only called when both primary provider runs return API errors for the same trial. It is not called simply because generated code fails evaluation.

## Run the application locally

The skill does not need these dependencies. Follow this section only if you want to run the Streamlit research app.

### Requirements

- Python 3.12, matching the current CI configuration
- Provider API credentials for Groq and Ollama Cloud
- A long, private application access password

### Windows setup

1. Clone the repository and open PowerShell in its folder.
2. Create and activate a virtual environment:

   ~~~powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ~~~

3. Install dependencies:

   ~~~powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ~~~

4. Copy the example environment file:

   ~~~powershell
   Copy-Item .env.example .env
   ~~~

5. Add your credentials to the local .env file, then start the app:

   ~~~powershell
   python -m streamlit run app.py
   ~~~

6. Open the local address printed by Streamlit, typically http://localhost:8501.

### Configuration

For Streamlit Community Cloud, configure these values under the app's **Settings → Secrets**. For local development, use the ignored .env file.

~~~toml
GROQ_API_KEY = "your-groq-api-key"
OLLAMA_API_KEY = "your-ollama-cloud-api-key"
PROMPTLAB_ACCESS_PASSWORD = "replace-with-a-long-random-password"

# Optional last-resort backup
GEMINI_API_KEY = "your-gemini-api-key"
~~~

The app remains locked unless PROMPTLAB_ACCESS_PASSWORD is configured. Never commit real API keys or share the app access password publicly. If the default Ollama model is unavailable to your account, configure OLLAMA_MODEL for a model you can access. Ollama Cloud's OpenAI-compatible endpoint is https://ollama.com/v1; see the [Ollama compatibility documentation](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx).

## Evaluation and security

- **AI-estimate mode:** estimates likely test outcomes; it does not run the generated Python code. Estimates must not be described as verified execution results.
- **Docker execution:** actual execution is available only when Docker is present and the app owner explicitly enables it. Review the deployment and sandbox configuration before enabling it for untrusted users.
- **Host-local execution:** direct host subprocess execution is not offered in the hosted UI and remains behind a developer-only environment guard.
- **Secrets and limits:** provider credentials are server-side; the app also uses an access-password gate, request/trial limits, and provider-error redaction.

Generated code is untrusted. These controls are defense in depth, not a guarantee of perfect isolation or a substitute for platform-level access restrictions and provider-side budgets. For a public hosted demo, prefer estimate mode unless you have reviewed and secured the execution environment.

## Testing

From the repository root, run:

~~~bash
python -m compileall -q app.py promptlab tests
python -m unittest discover -s tests -v
~~~

The GitHub Actions workflow also audits installed dependencies with pip-audit. Check the [CI workflow](https://github.com/Sahiljain6/promptlab/actions/workflows/ci.yml) for the latest status.

## Contributing

Issues and pull requests are welcome. Helpful contributions include new before-and-after transformations, reproducible prompt comparisons, documentation improvements, and security or compatibility reports.

Please avoid submitting API keys, private user data, or proprietary prompts without permission. When proposing quality improvements, include the original prompt, revised prompt, evaluation criteria, and observed results rather than making unsupported performance claims.

## License and reuse

This repository currently has no root-level LICENSE file. Public visibility alone does not specify all reuse and redistribution permissions. Before redistributing the files or incorporating them into another project, check with the repository owner about licensing terms.
