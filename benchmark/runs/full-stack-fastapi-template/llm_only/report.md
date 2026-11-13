# External dependencies — full-stack-fastapi-template

**3 external components** (2 cloud, 1 self-hosted).

Mode `llm_only` · LLM claude-cli / claude-opus-5-5 · 42 Python files · 0 LLM calls (382 cached) · 0.2 s

## Components

| component | hosting | version | used at | found by |
|---|---|---|---|---|
| `postgresql/database` | self-hosted | app==0.1.0 | `backend/app/alembic/env.py:68`, `backend/app/alembic/env.py:74`, `backend/app/alembic/env.py:86` (+66 more) | LLM (call site) · conf ≥ 0.60 |
| `sentry/errors` | cloud | sentry-sdk==2.70.0 | `backend/app/main.py:19` | LLM (call site) · conf ≥ 0.95 |
| `smtp/email` | cloud | app==0.1.0 | `backend/app/api/routes/login.py:67`, `backend/app/api/routes/users.py:73`, `backend/app/utils.py:56` | LLM (call site) · conf ≥ 0.75 |

## Hosting conflicts

- `smtp/email`: votes {'cloud': 2, 'self-hosted': 1}

## Files that could not be parsed

Their calls are missing from this report. A syntax error here usually means the code uses newer Python syntax than the interpreter running depscan — run it with a newer Python (e.g. `uvx --python 3.14 depscan ...`).

- backend/app/api/deps.py: SyntaxError: multiple exception types must be parenthesized (deps.py, line 36)

## How to read this

- **found by**: *known SDK* = a call into a well-known client library (no LLM); *LLM (call site)* / *LLM (package)* = an LLM read the surrounding code and named the service; *declared package* = static mode's guess from a dependency name. Lower confidence deserves a look.
- **version**: an exact pin from a lockfile or `==` requirement, else the declared range; *API vN* is a version written in the code (URL path or header).
- **Limits**: only Python code is scanned; code that ships but never runs (e.g. a legacy folder) is still reported unless excluded in pyproject.toml; names an LLM gave to one service are merged when they share a provider, hosting and directory (shown as *also named*), but a service can still appear twice.
- Full detail per component (every call site): `components.json`. What ran: `run_log.json`.
