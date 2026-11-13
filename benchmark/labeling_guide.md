# Labeling guide: external components

You are writing the ground truth for one repository: the list of external services its code depends on at runtime. Read the repository yourself and decide from the code. Your file is the answer key a tool will be scored against, so **be precise, conservative and explicit about doubt**.

## What counts as a component

A **component** is an external service the repository's code depends on at runtime, or the SDK/client that reaches it:

- a **cloud API** (e.g. an LLM API, a search API, a payments API, GitHub's REST API, a market-data API);
- a **database** or data store (SQLite file, Postgres, Redis, a vector DB) — including local/self-hosted ones;
- a **self-hosted service** the code talks to (Ollama, a Docker daemon, a message broker, a local headless browser it launches);
- a **model or dataset download** (Hugging Face Hub, a model file fetched on first use).

"At runtime" means: some non-test code path in the repository can call it when the program runs, including optional features behind a config flag or env var (an optional provider the user can select still counts).

## What does NOT count

- **Local-only libraries** that never leave the process (pydantic, numpy, PDF parsers, crypto/signing libraries, CLI/TUI frameworks, retry helpers, HTML parsers).
- **Inbound web frameworks** that *serve* the app (FastAPI, Flask, Django, uvicorn, Starlette) — the app's own server is not an external dependency.
- **Dispatch functions** that only choose a backend (`get_client()`, a provider router, an `env.execute()` that delegates). Label the concrete service the dispatch reaches, at the concrete call site, not the dispatcher.
- The repository's **own** backend called by its own frontend.
- **Mocks, stubs, fixtures** and anything used **only in tests** (`tests/`, `test_*.py`, `conftest.py`). Put test-only services in `ruled_out`.
- Plain local file I/O, local subprocesses that don't contact a server (e.g. running `git status`, `ls`).

## Scope: Python vs. other files

- Scope is the **Python runtime**. A component counts if the repository's Python code uses it.
- **Endpoints that appear only in non-Python files** (YAML, `.env.example`, `docker-compose.yml`, `.toml`, JSON configs) **count only if Python code consumes them** — e.g. Python reads a config key or env var whose value/default lives in that file. Use the Python consumption site as evidence and add the config file as a second evidence entry, and set `python_evidence: true`.
- If a service appears only in non-Python files and no Python code consumes it (e.g. an unused key in `.env.example`), it does **not** count — put it in `ruled_out`.
- If a service is used only by **JavaScript/TypeScript** (or another non-Python language) in the repo, record it in `out_of_scope`, not in `components`.

## Naming

- `canonical_name` is **lowercase `provider/service`**, using only `a-z 0-9 . -` in each part.
- `provider` = the organization or project that operates the service. `service` = the specific API or product.
- One component per distinct API product. Many endpoints of the same API are one component (all GitHub REST endpoints = `github/rest-api`). AWS/GCP/Azure services are separate components per service (`aws/s3`, `aws/sqs`).
- Prefer the most common, plain product name. Examples of the convention (not a list of what to look for): `aws/s3`, `github/rest-api`, `postgresql/database`, `sqlite/database`, `redis/redis`, `huggingface/hub`, `stripe/payments`, `slack/web-api`.
- **Configurable endpoints:** if the base URL comes from an env var or config with a default, name the **protocol** it speaks and record the default's provider in `default_target`. Example: an env-configurable OpenAI-compatible URL defaulting to `https://api.openai.com/v1` → `openai-compatible/chat-completions`, `default_target: "openai"`. If the code fixes a specific provider (a literal URL or a hard-coded base URL), name that provider instead (e.g. an OpenAI SDK pointed at a literal OpenRouter URL → `openrouter/chat-completions`).
- **Multi-provider client libraries** that route to whatever provider the runtime model string names (e.g. a "call any LLM" library) → one component named after the library's API (e.g. `<library>/completion`), plus a note. Separately label any provider the code *hard-codes*.
- **Hosted gateways** the code talks to directly (an LLM proxy/gateway service) → name the gateway.

## Hosting

`cloud` (operated by a third party over the internet) or `self-hosted` (runs on the user's machine or infrastructure: SQLite, a local Redis/Postgres, Ollama, a Docker daemon, a local headless browser).

## Versions

Record a version **only** when it is literally present:

- `version.api`: an API version in a URL path or header in the code, e.g. `v1`, `v8`, `2023-06-01`. Otherwise `null`.
- `version.package` + `version.package_name`: an **exact** pin of the client package in a lockfile (`uv.lock`, `poetry.lock`, `Pipfile.lock`) or an `==` pin in `requirements*.txt`/`pyproject.toml`. Ranges (`>=1.2`) don't count → `null`. Raw HTTP components usually have no package.
- Never infer a version from memory or from a package's general release history.

## Evidence

- 1–3 entries per component, each `path:line` relative to the repo root, with a short note. Prefer the **concrete call site** (the line that sends the request / opens the connection / constructs the client). Lines must exist.
- `python_evidence`: true if at least one evidence entry is a Python line that uses the service.

## ruled_out and notes

- `ruled_out`: things you suspected and rejected, each with a `location` (`path:line` or `path`) and a one-line reason. Include at least the obvious near-misses: dispatchers, local-only libraries that sound networky, test-only services, unused config entries. Aim for at least 5 if the repo has that many candidates.
- `notes` (top level and per component): anything ambiguous, and how you decided.
- `confidence` per component: 0–1, your own certainty that this is a real runtime component.

## Output

Write **one JSON file** matching `benchmark/labels/schema.json`:

```json
{
  "repo": "<repo folder name>",
  "repo_path": "<absolute path you labeled>",
  "labeled_by": "isolated subagent",
  "components": [
    {
      "canonical_name": "github/rest-api",
      "hosting": "cloud",
      "default_target": null,
      "version": {"api": null, "package": null, "package_name": null},
      "python_evidence": true,
      "evidence": [{"location": "src/github.py:52", "note": "requests.get to https://api.github.com/users/{u}"}],
      "confidence": 0.95,
      "notes": ""
    }
  ],
  "out_of_scope": [{"name": "vercel/analytics", "location": "web/app.tsx:3", "reason": "used only by the TypeScript frontend"}],
  "ruled_out": [{"target": "get_client()", "location": "src/llm/__init__.py:20", "reason": "dispatcher that only picks a provider"}],
  "notes": "free text"
}
```
