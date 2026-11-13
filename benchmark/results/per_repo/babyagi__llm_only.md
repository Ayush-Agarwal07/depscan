# babyagi — llm_only

TP 8 · FP 0 · FN 8

## True positives

| tool | label | matched by | tool evidence | label evidence |
|---|---|---|---|---|
| `sqlite/database` | `sqlite/database` | name | babyagi/functionz/db/db_router.py:46, babyagi/functionz/db/db_router.py:62, babyagi/functionz/db/db_router.py:80, babyagi/functionz/db/db_router.py:295, babyagi/functionz/db/db_router.py:298 | babyagi/functionz/db/local_db.py:14, babyagi/functionz/packs/drafts/user_db.py:46 |
| `litellm/completion` | `litellm/completion` | name | babyagi/functionz/packs/drafts/generate_function.py:824 | babyagi/functionz/packs/default/ai_functions.py:13, babyagi/functionz/packs/default/function_calling_chat.py:112, babyagi/functionz/packs/default/ai_functions.py:105 |
| `openai/chat-completions` | `openai/chat-completions` | name | babyagi/functionz/packs/default/ai_functions.py:13, babyagi/functionz/packs/default/function_calling_chat.py:112, babyagi/functionz/packs/default/function_calling_chat.py:154, babyagi/functionz/packs/drafts/choose_or_create_function.py:76, babyagi/functionz/packs/drafts/choose_or_create_function.py:164 | babyagi/functionz/packs/default/ai_functions.py:13, babyagi/functionz/packs/default/function_calling_chat.py:113, main.py:8 |
| `airtable/web-api` | `airtable/web-api` | name | babyagi/functionz/packs/plugins/airtable.py:18, babyagi/functionz/packs/plugins/airtable.py:34, babyagi/functionz/packs/plugins/airtable.py:51, babyagi/functionz/packs/plugins/airtable.py:69, babyagi/functionz/packs/plugins/airtable.py:86 | babyagi/functionz/packs/plugins/airtable.py:18, babyagi/functionz/packs/plugins/airtable.py:35 |
| `e2b/code-interpreter` | `e2b/code-interpreter` | name | babyagi/functionz/packs/plugins/e2b.py:17, babyagi/functionz/packs/plugins/e2b.py:19, babyagi/functionz/packs/plugins/e2b.py:61 | babyagi/functionz/packs/plugins/e2b.py:17, babyagi/functionz/packs/plugins/e2b.py:19 |
| `litellm/embeddings` | `openai/embeddings` | evidence | babyagi/functionz/packs/default/ai_functions.py:105 | babyagi/functionz/packs/default/ai_functions.py:105 |
| `augie/augies` | `augie/api` | evidence | babyagi/functionz/packs/plugins/augie.py:55, babyagi/functionz/packs/plugins/augie.py:58, babyagi/functionz/packs/plugins/augie.py:78, babyagi/functionz/packs/plugins/augie.py:81, babyagi/functionz/packs/plugins/augie.py:108 | babyagi/functionz/packs/plugins/augie.py:55, babyagi/functionz/packs/plugins/augie.py:78 |
| `wokelo/industry-primer` | `wokelo/api` | evidence | babyagi/functionz/packs/plugins/wokelo.py:21, babyagi/functionz/packs/plugins/wokelo.py:25, babyagi/functionz/packs/plugins/wokelo.py:44, babyagi/functionz/packs/plugins/wokelo.py:46, babyagi/functionz/packs/plugins/wokelo.py:46 | babyagi/functionz/packs/plugins/wokelo.py:21, babyagi/functionz/packs/plugins/wokelo.py:44 |

## False positives (tool only)

| tool | hosting | evidence (location · callee · route) |
|---|---|---|

## False negatives (label only)

| label | python evidence | evidence | label notes |
|---|---|---|---|
| `serpapi/search-api` | True | babyagi/functionz/packs/plugins/serpapi.py:35; babyagi/functionz/packs/plugins/serpapi.py:53 | Optional plugin pack, loadable via babyagi.load_functions('plugins/serpapi'); also a dependency of drafts/generate_function.py. |
| `firecrawl/api` | True | babyagi/functionz/packs/plugins/firecrawl.py:13; babyagi/functionz/packs/plugins/firecrawl.py:62; examples/custom_flask_example.py:16 | Optional plugin pack; firecrawl-py installed on demand by the executor. |
| `harmonic/api` | True | babyagi/functionz/packs/plugins/harmonic.py:28; babyagi/functionz/packs/plugins/harmonic.py:48 | Optional plugin pack. |
| `payman/api` | True | babyagi/functionz/packs/plugins/payman.py:44; babyagi/functionz/packs/plugins/payman.py:159 | Optional plugin pack. Production and sandbox hosts of the same PayMan API, chosen by a flag; one component. |
| `voilanorbert/api` | True | babyagi/functionz/packs/plugins/voilanorbert.py:28; babyagi/functionz/packs/plugins/voilanorbert.py:40 | Optional plugin pack; API version taken from URL path. |
| `postgresql/database` | True | babyagi/functionz/packs/drafts/user_db.py:48; babyagi/functionz/packs/drafts/user_db.py:63 | Only in the draft user_db pack and only via a db_type argument (default sqlite); all other user_db functions are SQLite-only. Kept as an optional user-selectable backend. |
| `mysql/database` | True | babyagi/functionz/packs/drafts/user_db.py:50; babyagi/functionz/packs/drafts/user_db.py:63 | Same caveat as postgresql/database: draft pack, optional db_type argument. |
| `pypi/package-index` | True | babyagi/functionz/core/execution.py:19 | Core executor installs missing per-function imports from the package index at runtime (e.g. pyairtable, firecrawl-py, e2b_code_interpreter for plugins). Included as a runtime network dependency; it is |
