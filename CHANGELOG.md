# Changelog

Scores are hybrid-mode F1 on the public benchmark set (see benchmark/README.md).

- **0.5.2** — Outputs record the repo's name instead of its absolute path. Benchmark ships with the 3 public repos only (`benchmark/fetch_repos.py`).
- **0.5.1** — Report: clearer inbound-framework line; explains parse failures (newer Python syntax).
- **0.5.0** — Raw-HTTP rule only for package calls or one constructor deep; class bodies are never wrappers.
- **0.4.0** — Per-endpoint names of one service are merged into one component (`merged_from` lists them). F1 0.58 → 0.67.
- **0.3.0** — Detects HTTP calls through injected clients (`self.deps.http.post(...)`).
- **0.2.0** — Built-in method names (`get`, `pop`, …) are no longer bare-matched as client calls; ~40% fewer LLM questions.
- **0.1.0** — First packaged release: CLI, Markdown report, providers (Anthropic API, Claude CLI, Ollama), answer cache. F1 0.58.
