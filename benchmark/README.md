# Benchmark

How we know whether depscan is right, and whether a change made it better. **Run it after any
change to `src/depscan/`.**

## What's here

| path | what |
|---|---|
| `repos.json` | the benchmark repos: path, URL, pinned commit |
| `fetch_repos.py` | clones them at the pinned commits into `benchmark/repos/` (git-ignored) |
| `labels/<repo>.json` | ground truth: the external services each repo really uses, with file:line evidence. **Frozen** (read-only; checksums in `labels/FROZEN*.sha256`) |
| `labeling_guide.md`, `labels/schema.json`, `validate_labels.py` | how labels are written and checked |
| `run.py` | runs depscan on every repo × mode → `runs/<repo>/<mode>/` |
| `score.py` | compares runs with labels → `results/results.md`, `results.csv`, `per_repo/*.md` |
| `results/match_adjudication.json` | scorer rules for names that must never count as a match (e.g. `web/arbitrary-url`) |
| `history/<version>.csv` | scores of every released version |
| `cache/` | cached LLM answers (not in git) — reruns cost nothing |
| `LOG.md` | every decision and result, in order |

The 3 repos are public projects that were labeled **before** depscan was tuned on anything, so
their scores are an honest estimate. (depscan was developed against a separate set of private
repos that isn't published.)

## Run it

```bash
python benchmark/fetch_repos.py                           # once: clone the repos at the pinned commits
python benchmark/run.py                                   # hybrid, all repos (resumable)
python benchmark/run.py --modes static,llm_only,hybrid    # all modes
python benchmark/score.py                                 # writes results/
cp benchmark/results/results.csv benchmark/history/<new-version>.csv
```

Needs the `claude` CLI (Claude Opus 5.5 on a Claude login) unless `--llm` says otherwise. A cold
hybrid run on these 3 repos is ~245 LLM questions (~$5 at list price, a few minutes); with the cache
it's seconds. `run.py` skips a repo × mode already run with the same depscan source, so an
interrupted run just continues.

## How scoring works

A tool component matches a labeled one by (1) the same name, else (2) evidence within ±3 lines in the
same file, else (3) the same provider — one-to-one. Precision = matched / tool components, recall =
matched / labels. **Strict F1** counts only exact-name matches; **name accuracy** = exact-name
share of matches; **versions** = labeled versions the tool got right. Micro-averaged over the repos.

## Current results (v0.5.2, Claude Opus 5.5)

| mode | P | R | F1 | LLM questions |
|---|---|---|---|---|
| hybrid | 0.92 | 0.52 | **0.67** | 245 |
| llm-only | 0.92 | 0.57 | **0.71** | 769 |
| static | 0.35 | 0.29 | 0.32 | 0 |

Per version: `history/` and `LOG.md`. Biggest remaining misses: plugin code loaded dynamically
(babyagi: 5 plugin APIs), URLs built from data tables, dead legacy folders, test-only usage.

## Adding a repo

1. Pick a repo the tool has never been tuned on; add it to `repos.json` with its URL, pinned commit, `set: "heldout"` and `path: "benchmark/repos/<name>"`.
2. Label it **before** looking at depscan's output on it: give an isolated reviewer (a person, or an
   LLM agent with no access to `src/` or `runs/`) only `labeling_guide.md`, `labels/schema.json` and
   `validate_labels.py`, and have them write `labels/<repo>.json`.
3. `python benchmark/validate_labels.py labels/<repo>.json` must print OK; then freeze it
   (`chmod a-w`, add its sha256 to a `FROZEN*.sha256` file). Never edit a frozen label — log
   mistakes in `LOG.md` instead.
4. Run and score as above.

Caveat: all labels so far were written by Claude agents and the tool's LLM step is also Claude —
they may share blind spots. Hand-checking a sample of labels (or adding human-labeled repos) is the
best next improvement to the benchmark itself.
