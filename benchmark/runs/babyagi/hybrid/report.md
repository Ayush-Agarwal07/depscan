# External dependencies — babyagi

**7 external components** (6 cloud, 1 self-hosted).

Mode `hybrid` · LLM claude-cli / claude-opus-5-5 · 40 Python files · 0 LLM calls (157 cached) · 0.4 s

## Components

| component | hosting | version | used at | found by |
|---|---|---|---|---|
| `airtable/web-api`<br>also named: `airtable/api` | cloud | — | `babyagi/functionz/packs/plugins/airtable.py:104`, `babyagi/functionz/packs/plugins/airtable.py:122`, `babyagi/functionz/packs/plugins/airtable.py:139` (+6 more) | LLM (call site) · conf ≥ 0.80 |
| `augie/augies`<br>also named: `augie/augies-status` | cloud | API v1 | `babyagi/functionz/packs/plugins/augie.py:108`, `babyagi/functionz/packs/plugins/augie.py:117`, `babyagi/functionz/packs/plugins/augie.py:55` (+3 more) | LLM (call site) · conf ≥ 0.80 |
| `e2b/code-interpreter` | cloud | — | `babyagi/functionz/packs/plugins/e2b.py:17`, `babyagi/functionz/packs/plugins/e2b.py:19`, `babyagi/functionz/packs/plugins/e2b.py:61` | LLM (call site) · conf ≥ 0.95 |
| `litellm/chat-completions` → openai<br>also named: `litellm/completion` | cloud | — | `babyagi/functionz/packs/default/ai_functions.py:105`, `babyagi/functionz/packs/default/ai_functions.py:13`, `babyagi/functionz/packs/default/function_calling_chat.py:112` (+11 more) | LLM (call site), LLM (package) · conf ≥ 0.80 |
| `openai/chat-completions` | cloud | — | `babyagi/functionz/packs/drafts/generate_function.py:759`, `babyagi/functionz/packs/drafts/generate_function.py:784`, `babyagi/functionz/packs/plugins/e2b.py:101` | LLM (call site) · conf ≥ 0.85 |
| `sqlite/database` | self-hosted | sqlalchemy >=1.4,<2.0 | `babyagi/functionz/db/db_router.py:295`, `babyagi/functionz/db/db_router.py:298`, `babyagi/functionz/db/db_router.py:46` (+62 more) | LLM (call site), LLM (package) · conf ≥ 0.75 |
| `wokelo/industry-primer`<br>also named: `wokelo/auth`, `wokelo/auth-token`, `wokelo/report-status`, `wokelo/reports`, `wokelo/reports-api` | cloud | API v3 | `babyagi/functionz/packs/plugins/wokelo.py:107`, `babyagi/functionz/packs/plugins/wokelo.py:112`, `babyagi/functionz/packs/plugins/wokelo.py:119` (+9 more) | LLM (call site) · conf ≥ 0.85 |

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
