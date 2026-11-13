# External dependencies — babyagi

**8 external components** (7 cloud, 1 self-hosted).

Mode `llm_only` · LLM claude-cli / claude-opus-5-5 · 40 Python files · 0 LLM calls (310 cached) · 0.4 s

## Components

| component | hosting | version | used at | found by |
|---|---|---|---|---|
| `airtable/web-api`<br>also named: `airtable/api` | cloud | — | `babyagi/functionz/packs/plugins/airtable.py:104`, `babyagi/functionz/packs/plugins/airtable.py:122`, `babyagi/functionz/packs/plugins/airtable.py:139` (+6 more) | LLM (call site) · conf ≥ 0.80 |
| `augie/augies`<br>also named: `augie/augies-status` | cloud | API v1 | `babyagi/functionz/packs/plugins/augie.py:108`, `babyagi/functionz/packs/plugins/augie.py:117`, `babyagi/functionz/packs/plugins/augie.py:55` (+3 more) | LLM (call site) · conf ≥ 0.80 |
| `e2b/code-interpreter` | cloud | — | `babyagi/functionz/packs/plugins/e2b.py:17`, `babyagi/functionz/packs/plugins/e2b.py:19`, `babyagi/functionz/packs/plugins/e2b.py:61` | LLM (call site) · conf ≥ 0.95 |
| `litellm/completion` → openai | cloud | — | `babyagi/functionz/packs/drafts/generate_function.py:824` | LLM (call site) · conf ≥ 0.80 |
| `litellm/embeddings` → openai | cloud | — | `babyagi/functionz/packs/default/ai_functions.py:105` | LLM (call site) · conf ≥ 0.82 |
| `openai/chat-completions` | cloud | — | `babyagi/functionz/packs/default/ai_functions.py:13`, `babyagi/functionz/packs/default/function_calling_chat.py:112`, `babyagi/functionz/packs/default/function_calling_chat.py:154` (+12 more) | LLM (call site) · conf ≥ 0.85 |
| `sqlite/database` | self-hosted | sqlalchemy >=1.4,<2.0 | `babyagi/functionz/db/db_router.py:295`, `babyagi/functionz/db/db_router.py:298`, `babyagi/functionz/db/db_router.py:46` (+8 more) | LLM (call site) · conf ≥ 0.70 |
| `wokelo/industry-primer`<br>also named: `wokelo/auth`, `wokelo/auth-token`, `wokelo/report-status`, `wokelo/reports`, `wokelo/reports-api` | cloud | API v3 | `babyagi/functionz/packs/plugins/wokelo.py:107`, `babyagi/functionz/packs/plugins/wokelo.py:112`, `babyagi/functionz/packs/plugins/wokelo.py:119` (+9 more) | LLM (call site) · conf ≥ 0.85 |

## Files that could not be parsed

Their calls are missing from this report. A syntax error here usually means the code uses newer Python syntax than the interpreter running depscan — run it with a newer Python (e.g. `uvx --python 3.14 depscan ...`).

- babyagi/functionz/packs/drafts/user_db.py: SyntaxError: invalid syntax (user_db.py, line 447)

## How to read this

- **found by**: *known SDK* = a call into a well-known client library (no LLM); *LLM (call site)* / *LLM (package)* = an LLM read the surrounding code and named the service; *declared package* = static mode's guess from a dependency name. Lower confidence deserves a look.
- **version**: an exact pin from a lockfile or `==` requirement, else the declared range; *API vN* is a version written in the code (URL path or header).
- **Limits**: only Python code is scanned; code that ships but never runs (e.g. a legacy folder) is still reported unless excluded in pyproject.toml; names an LLM gave to one service are merged when they share a provider, hosting and directory (shown as *also named*), but a service can still appear twice.
- Full detail per component (every call site): `components.json`. What ran: `run_log.json`.
