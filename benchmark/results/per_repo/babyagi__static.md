# babyagi — static

TP 2 · FP 3 · FN 14

## True positives

| tool | label | matched by | tool evidence | label evidence |
|---|---|---|---|---|
| `sqlalchemy/sdk` | `sqlite/database` | evidence | babyagi/functionz/db/local_db.py:14, babyagi/functionz/db/local_db.py:16, babyagi/functionz/db/local_db.py:16, babyagi/functionz/db/local_db.py:20, babyagi/functionz/db/local_db.py:23 | babyagi/functionz/db/local_db.py:14, babyagi/functionz/packs/drafts/user_db.py:46 |
| `litellm/sdk` | `litellm/completion` | evidence | babyagi/functionz/packs/default/ai_functions.py:13, babyagi/functionz/packs/default/ai_functions.py:105, babyagi/functionz/packs/default/function_calling_chat.py:112, babyagi/functionz/packs/default/function_calling_chat.py:154, babyagi/functionz/packs/drafts/choose_or_create_function.py:76 | babyagi/functionz/packs/default/ai_functions.py:13, babyagi/functionz/packs/default/function_calling_chat.py:112, babyagi/functionz/packs/default/ai_functions.py:105 |

## False positives (tool only)

| tool | hosting | evidence (location · callee · route) |
|---|---|---|
| `cryptography/sdk` | unknown | babyagi/functionz/db/models.py:22 · cryptography.fernet.Fernet.generate_key · known_sdk; babyagi/functionz/db/models.py:22 · cryptography.fernet.Fernet.generate_key().decode · known_sdk; babyagi/functionz/db/models.py:29 · cryptography.fernet.Fernet · known_sdk; babyagi/functionz/db/models.py:120 · cryptography.fernet.Fernet().decrypt · known_sdk; babyagi/functionz/db/models.py:120 · cryptography.fernet.Fernet().decrypt().decode · known_sdk; babyagi/functionz/db/models.py:129 · cryptography.fernet.Fernet().encrypt · known_sdk |
| `setuptools/sdk` | unknown | setup.py:15 · setuptools.setup · known_sdk; setup.py:24 · setuptools.find_packages · known_sdk |
| `sklearn/sdk` | unknown | babyagi/functionz/packs/default/ai_functions.py:199 · sklearn.metrics.pairwise.cosine_similarity · known_sdk |

## False negatives (label only)

| label | python evidence | evidence | label notes |
|---|---|---|---|
| `openai/chat-completions` | True | babyagi/functionz/packs/default/ai_functions.py:13; babyagi/functionz/packs/default/function_calling_chat.py:113; main.py:8 | Reached through litellm, but the model strings are hard-coded OpenAI models (no runtime model choice), so OpenAI is the effective hard-coded provider. Also drafts/*.py (gpt-4o-mini) and plugins/e2b.py |
| `openai/embeddings` | True | babyagi/functionz/packs/default/ai_functions.py:105 | Embedding model is a function parameter defaulting to OpenAI's text-embedding-ada-002; the caller could pass another litellm model string, but the default and the only in-repo callers use OpenAI. |
| `serpapi/search-api` | True | babyagi/functionz/packs/plugins/serpapi.py:35; babyagi/functionz/packs/plugins/serpapi.py:53 | Optional plugin pack, loadable via babyagi.load_functions('plugins/serpapi'); also a dependency of drafts/generate_function.py. |
| `firecrawl/api` | True | babyagi/functionz/packs/plugins/firecrawl.py:13; babyagi/functionz/packs/plugins/firecrawl.py:62; examples/custom_flask_example.py:16 | Optional plugin pack; firecrawl-py installed on demand by the executor. |
| `airtable/web-api` | True | babyagi/functionz/packs/plugins/airtable.py:18; babyagi/functionz/packs/plugins/airtable.py:35 | Optional plugin pack. |
| `e2b/code-interpreter` | True | babyagi/functionz/packs/plugins/e2b.py:17; babyagi/functionz/packs/plugins/e2b.py:19 | Optional plugin pack. E2B cloud sandbox. |
| `augie/api` | True | babyagi/functionz/packs/plugins/augie.py:55; babyagi/functionz/packs/plugins/augie.py:78 | Optional plugin pack; Augie Studio video generation API. |
| `harmonic/api` | True | babyagi/functionz/packs/plugins/harmonic.py:28; babyagi/functionz/packs/plugins/harmonic.py:48 | Optional plugin pack. |
| `payman/api` | True | babyagi/functionz/packs/plugins/payman.py:44; babyagi/functionz/packs/plugins/payman.py:159 | Optional plugin pack. Production and sandbox hosts of the same PayMan API, chosen by a flag; one component. |
| `voilanorbert/api` | True | babyagi/functionz/packs/plugins/voilanorbert.py:28; babyagi/functionz/packs/plugins/voilanorbert.py:40 | Optional plugin pack; API version taken from URL path. |
| `wokelo/api` | True | babyagi/functionz/packs/plugins/wokelo.py:21; babyagi/functionz/packs/plugins/wokelo.py:44 | Optional plugin pack. 'v3' appears only in the industry_primer endpoint path (not auth/assets endpoints), so it was treated as an endpoint/report version, not the API version; api left null. |
| `postgresql/database` | True | babyagi/functionz/packs/drafts/user_db.py:48; babyagi/functionz/packs/drafts/user_db.py:63 | Only in the draft user_db pack and only via a db_type argument (default sqlite); all other user_db functions are SQLite-only. Kept as an optional user-selectable backend. |
| `mysql/database` | True | babyagi/functionz/packs/drafts/user_db.py:50; babyagi/functionz/packs/drafts/user_db.py:63 | Same caveat as postgresql/database: draft pack, optional db_type argument. |
| `pypi/package-index` | True | babyagi/functionz/core/execution.py:19 | Core executor installs missing per-function imports from the package index at runtime (e.g. pyairtable, firecrawl-py, e2b_code_interpreter for plugins). Included as a runtime network dependency; it is |
