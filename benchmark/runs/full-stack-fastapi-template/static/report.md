# External dependencies — full-stack-fastapi-template

**8 external components** (1 cloud, 0 self-hosted, 7 unknown).

Mode `static` · LLM none (static mode) · 42 Python files · 0 LLM calls (0 cached) · 0.2 s

## Components

| component | hosting | version | used at | found by |
|---|---|---|---|---|
| `app/sdk` | unknown | app==0.1.0 | `backend/app/api/routes/items.py:113`, `backend/app/api/routes/items.py:44`, `backend/app/api/routes/items.py:45` (+127 more) | declared package |
| `emails/sdk` | unknown | emails==1.1.2 | `backend/app/utils.py:42`, `backend/app/utils.py:56` | declared package |
| `jinja2/sdk` | unknown | jinja2==3.1.6 | `backend/app/utils.py:29`, `backend/app/utils.py:30` | declared package |
| `pwdlib/sdk` | unknown | pwdlib==0.3.1 | `backend/app/core/security.py:11`, `backend/app/core/security.py:13`, `backend/app/core/security.py:14` (+8 more) | declared package |
| `pydantic-settings/sdk` | unknown | pydantic-settings==2.15.0 | `backend/app/core/config.py:16` | declared package |
| `sentry/errors` | cloud | sentry-sdk==2.70.0 | `backend/app/main.py:19` | known SDK |
| `sqlalchemy/sdk` | unknown | sqlalchemy==2.0.51 | `backend/app/alembic/env.py:68`, `backend/app/alembic/env.py:74`, `backend/app/alembic/versions/1a31ce608336_add_cascade_delete_relationships.py:23` (+50 more) | declared package |
| `sqlmodel/sdk` | unknown | sqlmodel==0.0.47 | `backend/app/alembic/versions/e2412789c190_initialize_models.py:23`, `backend/app/alembic/versions/e2412789c190_initialize_models.py:26`, `backend/app/alembic/versions/e2412789c190_initialize_models.py:29` (+87 more) | declared package |

## Not counted

- Inbound web frameworks serving this app (fastapi, 72 call sites): these serve requests; they aren't external services.

## Files that could not be parsed

Their calls are missing from this report. A syntax error here usually means the code uses newer Python syntax than the interpreter running depscan — run it with a newer Python (e.g. `uvx --python 3.14 depscan ...`).

- backend/app/api/deps.py: SyntaxError: multiple exception types must be parenthesized (deps.py, line 36)

## How to read this

- **found by**: *known SDK* = a call into a well-known client library (no LLM); *LLM (call site)* / *LLM (package)* = an LLM read the surrounding code and named the service; *declared package* = static mode's guess from a dependency name. Lower confidence deserves a look.
- **version**: an exact pin from a lockfile or `==` requirement, else the declared range; *API vN* is a version written in the code (URL path or header).
- **Limits**: only Python code is scanned; code that ships but never runs (e.g. a legacy folder) is still reported unless excluded in pyproject.toml; names an LLM gave to one service are merged when they share a provider, hosting and directory (shown as *also named*), but a service can still appear twice.
- Full detail per component (every call site): `components.json`. What ran: `run_log.json`.
