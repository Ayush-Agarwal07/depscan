# depscan

**Find the external services a Python codebase depends on** — cloud APIs, databases, self-hosted
services, model downloads — with the file and line where each one is used.

```
$ depscan ~/code/full-stack-fastapi-template
[1/4] scanning ~/code/full-stack-fastapi-template ...
      42 Python files, 880 call sites -> 362 SDK calls, 20 unclear, 1 files failed to parse
[2/4] routing (hybrid) ...
      1 resolved statically, 72 inbound-framework calls set aside, 27 questions for the LLM
[3/4] LLM provider: claude-cli (auto-detected), model claude-opus-5-5; cache ~/.cache/depscan
      27 answers (27 new calls, 0 cached), 0 invalid
[4/4] merging ...

3 external components found:
  postgresql/database                      self-hosted
  sentry/errors                            cloud
  smtp/email                               self-hosted

Report: ./depscan-report/full-stack-fastapi-template/report.md
```

(Real output on the public `fastapi/full-stack-fastapi-template`, 28 s from a fresh install.)

It answers questions like *"what would break if we lost network access?"*, *"which vendors does this
app talk to?"*, *"where do we call OpenAI, and on which API version?"*

## How it works (one paragraph)

depscan reads every `.py` file with Python's own parser (it never runs your code). Calls into
well-known SDKs (`openai`, `anthropic`, `boto3`, `redis`, …) are named directly from a built-in table.
Calls it can't name on its own — raw HTTP requests, your own wrapper functions, database drivers,
injected clients — are sent with ~20 lines of surrounding code to an LLM, which says whether the call
reaches an external service and which one. The answers are merged into one component per service.
Details: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## Install

Needs Python 3.11+.

```bash
git clone <this repo> depscan
uv tool install ./depscan          # or: pipx install ./depscan
# for the Anthropic API provider:  uv tool install './depscan[anthropic]'
depscan --version
```

## Use

```bash
depscan PATH                       # default: hybrid mode, LLM auto-detected
depscan PATH --dry-run             # show how many LLM questions would be sent; send nothing
depscan PATH --llm none            # static only: no LLM, nothing leaves your machine
depscan PATH -o out/ --json        # choose the output folder; also print JSON to stdout
```

Output folder (default `./depscan-report/<repo-name>/`):

| file | what it is |
|---|---|
| `report.md` | **start here** — one table row per service: hosting, version, where it's used, how it was found |
| `components.json` | the same, machine-readable, every call site ([docs/OUTPUT.md](docs/OUTPUT.md)) |
| `run_log.json` | what ran: mode, provider, model, LLM calls, tokens, cost, timings |
| `work/` | intermediate files, for debugging |

### Choosing an LLM provider

`--llm auto` (the default) uses the first that works:

| provider | needs | notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` + the `[anthropic]` extra | billed to the API key |
| `claude-cli` | [Claude Code](https://claude.com/claude-code) installed and logged in (`claude`) | runs on your Claude subscription; each call is isolated (no tools, no project files) |
| `ollama` | a local Ollama server | everything stays on your machine; smaller models are less accurate (`--model` to pick one) |
| `none` | — | static mode: only known SDK calls are reported |

If nothing is available, depscan falls back to static mode and says so. Default model:
`claude-opus-5-5` (Claude providers), `gemma4:12b` (Ollama); override with `--model`.

**Cost and time** (Claude Opus 5.5, from the benchmark): ~30–200 LLM questions for a typical
small/medium repo, ~1–3 minutes, roughly $0.02 per question at list price. Answers are cached in
`~/.cache/depscan`, so re-running on an unchanged repo makes no LLM calls. Use `--dry-run` to see
the count first.

### What leaves your machine

In `hybrid` and `llm-only` modes, each LLM question contains ~20 lines of code around one call, the
file's import lines and (for local wrappers) the wrapper's source. Nothing else is sent. With
`--llm none` or `--llm ollama` nothing leaves your machine. depscan never executes the scanned code;
`--installed-versions` is the one exception (it runs the repo's own `.venv/bin/python` to read
installed package versions) and is off by default.

### Modes

- `hybrid` (default, recommended): known SDKs named without the LLM; everything else asked.
- `static`: no LLM; fast and private, but misses raw HTTP calls, wrappers and anything unusual.
- `llm-only`: every candidate call goes to the LLM — about 2.6× the questions of hybrid. On the held-out
  set it found slightly more (F1 0.71 vs 0.67); use it when recall matters more than cost.

## Configure for a repo (optional)

In the scanned repo's `pyproject.toml`:

```toml
[tool.depscan]
skip = ["benchmark", "scripts/one_off"]   # directories not scanned at all
exclude = ["legacy*"]                     # still scanned, but reported under "only in excluded code"
```

`[tool.setuptools.packages.find].exclude` patterns (e.g. `tests*`, `deprecated*`) are honoured the
same way as `exclude`.

## Accuracy and limits

Measured on 3 public repos whose answers were written by isolated Claude agents before any tuning
(the tool was developed on a separate, private set of repos); depscan's LLM step was Claude Opus 5.5 —
see [benchmark/README.md](benchmark/README.md):

| mode | precision | recall | F1 | LLM questions (3 repos) |
|---|---|---|---|---|
| hybrid (default) | 0.92 | 0.52 | **0.67** | 245 |
| llm-only | 0.92 | 0.57 | **0.71** | 769 |
| static | 0.35 | 0.29 | 0.32 | 0 |

In plain words: when depscan names a service it's almost always right; it finds about half of them.

What it does **not** do:
- **Python only.** JavaScript/TypeScript, Go, etc. aren't scanned.
- **Parses with the Python running depscan.** Code using newer syntax than that interpreter (e.g. 3.14's
  unparenthesized `except A, B:`) can't be parsed; those files are listed in the report. Run depscan with
  a recent Python: `uvx --python 3.14 --from ./depscan depscan PATH`.
- **Dynamic code is missed** — functions loaded from strings/plugins at runtime, URLs built from data
  tables (one call that hits five sites is reported once, or as an arbitrary URL), shell-outs
  (`subprocess.run(["curl", ...])`, `docker run`).
- **Dead code is reported** — a legacy folder that ships but never runs still shows up; exclude it.
- **Test-only services are reported** unless your tests are excluded in `pyproject.toml`.
- Names are the LLM's: one service can occasionally still appear under two names.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'depscan'` from a virtualenv inside `~/Documents` or
  `~/Desktop` on macOS** — iCloud sync marks `.pth` files hidden and Python 3.13 skips hidden ones.
  Keep the venv outside synced folders, use `uv tool install`, or run
  `chflags nohidden .venv/lib/python3.*/site-packages/*.pth`.
- **`--llm claude-cli is not usable`** — install Claude Code and run `claude` once to log in.
- **Rate limits** — answers so far are cached; re-run the same command to continue.

## Develop

```bash
uv venv && uv pip install -e '.[dev]'
pytest                                   # offline tests, no LLM
python benchmark/fetch_repos.py && python benchmark/run.py && python benchmark/score.py   # see benchmark/README.md
```

Maintainer guide: [docs/MAINTAINING.md](docs/MAINTAINING.md).

Code map: `src/depscan/` — `scan.py` (static analysis) → `prepare.py` (routing, URL tracing) →
`classify.py` (LLM) → `merge.py` (components) → `report.py`; `pipeline.py` runs them, `cli.py` is the
command, `aliases.py` is the known-SDK table.

## License

MIT — see [LICENSE](LICENSE).
