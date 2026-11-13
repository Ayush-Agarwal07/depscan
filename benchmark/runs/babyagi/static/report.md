# External dependencies — babyagi

**5 external components** (0 cloud, 0 self-hosted, 5 unknown).

Mode `static` · LLM none (static mode) · 40 Python files · 0 LLM calls (0 cached) · 0.4 s

## Components

| component | hosting | version | used at | found by |
|---|---|---|---|---|
| `cryptography/sdk` | unknown | — | `babyagi/functionz/db/models.py:120`, `babyagi/functionz/db/models.py:120`, `babyagi/functionz/db/models.py:129` (+3 more) | declared package |
| `litellm/sdk` | unknown | — | `babyagi/functionz/packs/default/ai_functions.py:105`, `babyagi/functionz/packs/default/ai_functions.py:13`, `babyagi/functionz/packs/default/function_calling_chat.py:112` (+10 more) | declared package |
| `setuptools/sdk` | unknown | setuptools==75.1.0 | `setup.py:15`, `setup.py:24` | declared package |
| `sklearn/sdk` | unknown | — | `babyagi/functionz/packs/default/ai_functions.py:199` | declared package |
| `sqlalchemy/sdk` | unknown | sqlalchemy >=1.4,<2.0 | `babyagi/functionz/db/local_db.py:14`, `babyagi/functionz/db/local_db.py:16`, `babyagi/functionz/db/local_db.py:16` (+57 more) | declared package |

## Not counted

- Inbound web frameworks serving this app (flask, 76 call sites): these serve requests; they aren't external services.

## Files that could not be parsed

Their calls are missing from this report. A syntax error here usually means the code uses newer Python syntax than the interpreter running depscan — run it with a newer Python (e.g. `uvx --python 3.14 depscan ...`).

- babyagi/functionz/packs/drafts/user_db.py: SyntaxError: invalid syntax (user_db.py, line 447)

## How to read this

- **found by**: *known SDK* = a call into a well-known client library (no LLM); *LLM (call site)* / *LLM (package)* = an LLM read the surrounding code and named the service; *declared package* = static mode's guess from a dependency name. Lower confidence deserves a look.
- **version**: an exact pin from a lockfile or `==` requirement, else the declared range; *API vN* is a version written in the code (URL path or header).
- **Limits**: only Python code is scanned; code that ships but never runs (e.g. a legacy folder) is still reported unless excluded in pyproject.toml; names an LLM gave to one service are merged when they share a provider, hosting and directory (shown as *also named*), but a service can still appear twice.
- Full detail per component (every call site): `components.json`. What ran: `run_log.json`.
