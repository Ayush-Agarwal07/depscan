# Maintaining depscan

## Read in this order

1. `README.md` — install, use, providers, limits.
2. `docs/HOW_IT_WORKS.md` — the 4-step pipeline and where to change what.
3. `benchmark/README.md` — how accuracy is measured; run it after every change.
4. `benchmark/LOG.md` — decisions and results so far; `CHANGELOG.md` — per version.

## First-day checklist

```bash
uv venv && uv pip install -e '.[dev]'     # on macOS, keep the venv out of iCloud-synced folders
pytest                                    # offline tests, no LLM
depscan tests/fixtures/sample_app --llm none
depscan <some repo> --dry-run             # what an LLM run would send
python benchmark/fetch_repos.py && python benchmark/run.py && python benchmark/score.py
```

## Rules of the road

- One behavior change per release; benchmark it; save `benchmark/results/results.csv` as
  `benchmark/history/<version>.csv`; add a line to `CHANGELOG.md` and `benchmark/LOG.md`.
- Never edit a frozen label in `benchmark/labels/`; log mistakes in `benchmark/LOG.md`.
- Changing `SYSTEM_PROMPT` in `classify.py` invalidates every cached LLM answer — batch prompt changes.
- New benchmark repos must be labeled before you look at depscan's output on them.

## Open items, by value

1. Default-exclude tests (`tests/`, `test_*.py`) — removes test-only false positives; small change.
2. Human spot-check of the labels (all were written by Claude agents, the same model family as the
   tool's LLM step).
3. Dynamic plugin code (babyagi-style `load_functions`) and URL template tables — the biggest recall
   losses.
4. Narrow the `web/arbitrary-url` prompt rule — together with any other prompt change.
5. Other languages (JS/TS first) — a new scanner; classify/merge can be reused.
