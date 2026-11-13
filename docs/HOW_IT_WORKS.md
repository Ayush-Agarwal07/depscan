# How depscan works

Four steps, each a module in `src/depscan/`, run in order by `pipeline.py`. Every step writes its
output to `<out>/work/`, so you can inspect exactly what each one decided.

```
 repo/*.py ──► 1 scan ──► 2 prepare ──► 3 classify ──► 4 merge ──► report.md, components.json
              (ast)      (route)        (LLM, cached)   (combine)
```

## 1. scan.py — static analysis (no LLM, never runs code)

- Finds every `.py` file (skips `.venv`, `node_modules`, build dirs, and `[tool.depscan].skip`),
  parses it with `ast`, and detects import roots (`src/` layouts, `backend/` subfolders).
- Reads dependency files anywhere in the repo: `requirements*.txt`, `pyproject.toml`, `uv.lock`,
  `poetry.lock`, `Pipfile.lock` → package name, exact pin or range.
- Resolves every call to a dotted name through imports and simple assignments
  (`client = openai.OpenAI()` → `client.chat.completions.create` = `openai.OpenAI().chat.completions.create`).
- Sorts each call into:
  - **known SDK** — into a declared third-party package;
  - **unclear** — needs judgment: `raw_http` (`requests`, `httpx`, `urllib`…), `client_call` (an HTTP
    verb on an injected client attribute, e.g. `self.deps.http.post`), `stdlib_client` (`sqlite3`,
    `smtplib`, `socket`…), `wrapper` (a call to your own function that itself makes an external
    call), `dynamic_client` (a method of a client chosen at runtime), `undeclared` (a package missing
    from the dependency files);
  - **ignored** — stdlib and purely local code.

Output: `work/scan/known_sdk.json`, `unclear.json`, `scan_meta.json`.

## 2. prepare.py — routing

Decides what goes to the LLM, depending on the mode:

- **hybrid**: SDK calls in the alias table (`aliases.py`, ~40 common SDKs) are named immediately;
  other declared packages get **one LLM question per package** (with 3 sample call sites); every
  unclear call gets one question. Inbound web frameworks (FastAPI, Flask, …) are set aside — they
  serve the app, they aren't dependencies.
- **static**: SDK calls only, named from the alias table or as `<package>/sdk`; unclear calls dropped.
- **llm_only**: every candidate call is asked, no static shortcuts.

For URLs like `f"{self.base_url}/chat"`, it traces `self.base_url` back to where its value comes from
(assignments, constructor arguments, settings defaults) and adds those lines to the question.

Output: `work/llm_inputs.json`, `static_resolved.json`, `folded.json`, `prepare_stats.json`.

## 3. classify.py — the LLM step

Each question is the code context plus a fixed system prompt with 7 worked examples. The model
answers with JSON (`is_external_api`, `canonical_name` like `stripe/payments`, `hosting`,
`version_hint`, `confidence`, `reasoning`), enforced by a JSON schema. Rules worth knowing:

- **Dispatch sites** (a factory or router that only picks a backend) are answered "not external";
  the concrete call site is what counts.
- A `version_hint` is kept only if that exact string appears in the code — the model can't invent one.
- Invalid answers are retried up to 3 times, with the validation error fed back.
- **Cache**: every answer is stored under `~/.cache/depscan/<sha256>.json`, keyed by provider, model,
  prompt and context. Same code → no new calls. Changing the prompt or model invalidates it.

Output: `work/llm_results.json`, `classify_stats.json`.

## 4. merge.py — one component per service

- Combines static names and LLM answers; normalizes spellings (`Hugging Face` → `huggingface`).
- **Merges per-endpoint names** of one service: names with the same provider, the same hosting and
  evidence in a shared directory become one component (`acme/events` + `acme/orders` →
  one component, listing both in `merged_from`). Multi-product providers (aws, gcp, azure, google,
  microsoft) are never merged this way.
- Versions: exact package pin (lockfile or `==`) for SDK-backed components; `api_version` only from
  the code; `installed_version` only with `--installed-versions`.
- Evidence under excluded paths is flagged; a component whose evidence is all excluded is reported
  separately.

Output: `components.json` (schema in [OUTPUT.md](OUTPUT.md)); `report.py` renders `report.md`.

## Where to change things

| want to… | edit |
|---|---|
| name a new SDK without the LLM | `aliases.py` → `SDK_ALIASES` |
| treat a library as never-external | `scan.py` → `LOCAL_ONLY_PACKAGES` |
| detect a new kind of network call | `scan.py` → `preliminary()` |
| change what the LLM is told | `classify.py` → `SYSTEM_PROMPT` (invalidates the cache; re-run the benchmark) |
| change how names are merged | `merge.py` → `consolidate()` |

After any change: `pytest`, then the benchmark (`benchmark/README.md`) to see whether it helped.
