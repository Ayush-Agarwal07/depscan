# External dependencies — shell_gpt

**4 external components** (1 cloud, 0 self-hosted, 3 unknown).

Mode `static` · LLM none (static mode) · 28 Python files · 0 LLM calls (0 cached) · 0.2 s

## Components

| component | hosting | version | used at | found by |
|---|---|---|---|---|
| `click/sdk` | unknown | click >= 8.0.0 | `sgpt/app.py:190`, `sgpt/app.py:195`, `sgpt/app.py:198` (+7 more) | declared package |
| `distro/sdk` | unknown | distro >= 1.8.0, < 2.0.0 | `sgpt/role.py:120` | declared package |
| `openai/chat-completions` | cloud | openai >= 2.0.0, < 3.0.0 | `sgpt/handlers/handler.py:123`, `sgpt/handlers/handler.py:171`, `sgpt/handlers/handler.py:31` (+3 more) | known SDK |
| `prompt-toolkit/sdk` | unknown | prompt-toolkit >= 3.0.51 | `sgpt/app.py:241`, `sgpt/app.py:256` | declared package |

## How to read this

- **found by**: *known SDK* = a call into a well-known client library (no LLM); *LLM (call site)* / *LLM (package)* = an LLM read the surrounding code and named the service; *declared package* = static mode's guess from a dependency name. Lower confidence deserves a look.
- **version**: an exact pin from a lockfile or `==` requirement, else the declared range; *API vN* is a version written in the code (URL path or header).
- **Limits**: only Python code is scanned; code that ships but never runs (e.g. a legacy folder) is still reported unless excluded in pyproject.toml; names an LLM gave to one service are merged when they share a provider, hosting and directory (shown as *also named*), but a service can still appear twice.
- Full detail per component (every call site): `components.json`. What ran: `run_log.json`.
