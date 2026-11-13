# External dependencies — shell_gpt

**2 external components** (2 cloud, 0 self-hosted).

Mode `hybrid` · LLM claude-cli / claude-opus-5-5 · 28 Python files · 0 LLM calls (61 cached) · 0.2 s

## Components

| component | hosting | version | used at | found by |
|---|---|---|---|---|
| `openai-compatible/chat-completions` → openai | cloud | — | `sgpt/handlers/handler.py:159` | LLM (call site) · conf ≥ 0.75 |
| `openai/chat-completions` | cloud | openai >= 2.0.0, < 3.0.0 | `sgpt/handlers/handler.py:123`, `sgpt/handlers/handler.py:171`, `sgpt/handlers/handler.py:31` (+3 more) | known SDK |

## How to read this

- **found by**: *known SDK* = a call into a well-known client library (no LLM); *LLM (call site)* / *LLM (package)* = an LLM read the surrounding code and named the service; *declared package* = static mode's guess from a dependency name. Lower confidence deserves a look.
- **version**: an exact pin from a lockfile or `==` requirement, else the declared range; *API vN* is a version written in the code (URL path or header).
- **Limits**: only Python code is scanned; code that ships but never runs (e.g. a legacy folder) is still reported unless excluded in pyproject.toml; names an LLM gave to one service are merged when they share a provider, hosting and directory (shown as *also named*), but a service can still appear twice.
- Full detail per component (every call site): `components.json`. What ran: `run_log.json`.
