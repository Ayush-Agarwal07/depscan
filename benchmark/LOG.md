# Benchmark log

Decisions and results while turning a research prototype into depscan and improving it.

## Packaging (0.1.0)

- P-1 depscan 0.1.0 is the prototype repackaged: modules under `src/depscan/`, each step's `main()`
  turned into a parameterized `run()`, plus `pipeline.py` (one in-process run), `cli.py` and
  `report.py`. The LLM prompt, routing and output formats were not changed.
- P-2 Regression check: with the prototype's LLM-answer cache, all 15 of its benchmark runs (5 repos ×
  static/hybrid/llm_only) were reproduced byte-for-byte (LLM inputs, static resolutions, components)
  with 0 new LLM calls — 0.1.0 is behaviorally identical to the benchmarked prototype.
- P-3 User-visible changes: reading installed versions (which runs the scanned repo's own
  `.venv/bin/python`) became opt-in (`--installed-versions`); the cache moved to `~/.cache/depscan`;
  env vars are `DEPSCAN_*`; repo config lives in `[tool.depscan]`.
- P-4 macOS gotcha: a virtualenv inside an iCloud-synced folder (`~/Documents`, `~/Desktop`) gets its
  `.pth` files marked hidden, and Python 3.13 skips hidden `.pth` files, so an editable install stops
  importing. `benchmark/run.py` and pytest put `src/` on the path themselves; README → Troubleshooting.

## Benchmark sets

- H-1 Development was done against 5 private repos (not published). For an honest estimate, 3 public
  repos were added as a held-out set, chosen for variety: `fastapi/full-stack-fastapi-template`
  (monorepo, `uv.lock` workspace, TypeScript frontend), `TheR1D/shell_gpt` (small CLI),
  `yoheinakajima/babyagi` (`poetry.lock`, plugin packs). Pinned commits in `repos.json`.
- H-2 The held-out repos were labeled by isolated Claude agents (given only the labeling guide, the schema,
  the validator and the repo) **before any accuracy fix was written**, then frozen (read-only;
  `labels/FROZEN_HELDOUT.sha256`). 21 components (3 + 2 + 16).
- H-3 The labelers' summaries reached the developer's context, so the fixes implemented were exactly the
  five announced *before* labeling started; none was designed from held-out labels or held-out output.
- H-4 Label issue (logged, not fixed): `labels/shell_gpt.json`'s ruled_out entry for `requests-mock`
  cites `pyproject.toml:44`; the dependency is on line 42 (ruled_out isn't scored).
- H-5 For publication (0.5.2) the 5 private repos' labels and runs were removed and `repo_path` in the 3
  public labels was changed from an absolute local path to `benchmark/repos/<name>` — the only edit to
  frozen labels (all other fields verified identical; new checksums in `FROZEN_HELDOUT.sha256`).

## Accuracy fixes — one per release, each benchmarked

Hybrid mode, Claude Opus 5.5. Held-out = the 3 public repos; dev = the private set (aggregate only).

| version | change | dev F1 | held-out F1 (P / R) | LLM questions (all 8) |
|---|---|---|---|---|
| 0.1.0 | packaged, no behavior change | 0.56 | 0.58 (0.60 / 0.57) | 1278 |
| 0.2.0 | fix 3: never bare-match built-in method names (`.get` …) | 0.50 | 0.58 (0.60 / 0.57) | 776 |
| 0.3.0 | fix 2: HTTP calls through injected client attributes | 0.59 | 0.58 (0.60 / 0.57) | 790 |
| 0.4.0 | fix 1: merge one service's per-endpoint names | 0.75 | **0.67 (0.92 / 0.52)** | 790 |
| 0.5.0 | fix 5: raw-HTTP verb rule one constructor deep; class bodies never wrappers | 0.77 | 0.67 (0.92 / 0.52) | 726 |

- F-1 Fix 3 alone cut LLM questions by 40% but dropped dev recall: in one dev repo the real requests
  (`self.deps.http.get(...)`) had only been caught through accidental `.get` matching. Fix 2 recovered
  them, plus two services the scanner had never surfaced. Fixes 2 and 3 didn't change held-out scores.
- F-2 Fix 1's rule was widened from "same file, class or host" to "same directory" after dev-set errors
  (per-endpoint client files side by side), decided before seeing held-out results for it. Held-out
  precision 0.60 → 0.92; recall −1 component on babyagi, where two names that happened to match two
  different labels (litellm, OpenAI) are now one component — reported, not tuned.
- F-3 Fix 4 (narrow the `web/arbitrary-url` prompt rule) deferred: a prompt change invalidates the whole
  answer cache for about one false positive.
- F-4 On the held-out set `llm_only` beats hybrid (F1 0.71 vs 0.67) at 3.1× the questions; hybrid stays
  the default for cost.
- F-5 Checks on 0.5.x: every hybrid re-run makes 0 LLM calls with byte-identical output; `score.py`
  output is identical across runs; a fresh `uvx --from ./depscan` install ran on
  full-stack-fastapi-template with an empty cache in 28 s (27 calls, 0 invalid, 3/3 labeled services).
- F-6 depscan parses with its own Python: full-stack-fastapi-template's `backend/app/api/deps.py` uses
  3.14 syntax and fails under 3.13. Documented; the report explains parse failures.
- F-7 0.5.2 records the repo name instead of its absolute path in outputs; the public benchmark re-ran from
  `benchmark/repos/` entirely from cache (0 new calls) with identical scores.

## Next steps

- Default-exclude tests (`tests/`, `test_*.py`) — removes test-only false positives.
- A human spot-check of the labels (all were written by Claude agents, the same model family as the
  tool's LLM step).
- Dynamic plugin loading, URL template tables, shell-outs, dead-code reachability, non-Python languages.
