"""depscan command line.

    depscan PATH                      # hybrid mode, auto-detected LLM, report in ./depscan-report/<repo>/
    depscan PATH --llm none           # static only: no LLM, nothing leaves your machine
    depscan PATH --dry-run            # show how many LLM questions would be sent, send nothing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depscan import __version__
from depscan.pipeline import DepscanError, run

MODE_ALIASES = {"hybrid": "hybrid", "static": "static", "llm-only": "llm_only", "llm_only": "llm_only"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="depscan",
        description="Inventory the external services a Python repository depends on "
                    "(cloud APIs, databases, self-hosted services, model downloads).",
        epilog="Docs: README.md. Output: report.md (read this), components.json, run_log.json.",
    )
    p.add_argument("repo", type=Path, help="path to the repository to scan")
    p.add_argument("-o", "--out", type=Path, help="output directory (default: ./depscan-report/<repo-name>)")
    p.add_argument("--mode", choices=["hybrid", "static", "llm-only"], default="hybrid",
                   help="hybrid (default): known SDKs statically, the rest by LLM; static: no LLM; "
                        "llm-only: every candidate call by LLM (slowest, for comparison)")
    p.add_argument("--llm", choices=["auto", "claude-cli", "anthropic", "ollama", "none"], default="auto",
                   help="LLM provider. auto = ANTHROPIC_API_KEY, else the `claude` CLI, else local Ollama, "
                        "else fall back to static. none = static mode.")
    p.add_argument("--model", help="model name (default: claude-opus-5-5 for Claude providers, gemma4:12b for Ollama)")
    p.add_argument("--cache-dir", type=Path, help="LLM answer cache (default: ~/.cache/depscan)")
    p.add_argument("--workers", type=int, default=4, help="parallel LLM calls (default 4)")
    p.add_argument("--installed-versions", action="store_true",
                   help="also read installed versions by running the repo's own .venv/bin/python "
                        "(executes code from the scanned repo — only use on repos you trust)")
    p.add_argument("--dry-run", action="store_true", help="scan and route, then report what would be sent; no LLM calls")
    p.add_argument("--json", action="store_true", help="print components.json to stdout when done")
    p.add_argument("-q", "--quiet", action="store_true", help="no progress output")
    p.add_argument("--version", action="version", version=f"depscan {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    out = args.out or Path.cwd() / "depscan-report" / repo.name
    log = (lambda *a, **k: None) if args.quiet else (lambda msg: print(msg, file=sys.stderr))
    try:
        result = run(repo, out, mode=MODE_ALIASES[args.mode], llm=args.llm, model=args.model,
                     cache_dir=args.cache_dir, workers=args.workers,
                     installed_versions=args.installed_versions, dry_run=args.dry_run, log=log)
    except DepscanError as exc:
        print(f"depscan: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("depscan: interrupted (LLM answers so far are cached; rerun to resume)", file=sys.stderr)
        return 130
    if result.get("dry_run"):
        return 0
    comps = result["components"]
    live = [c for c in comps if not c.get("excluded")]
    log(f"\n{len(live)} external components found" + (f" (+{len(comps) - len(live)} only in excluded code)"
                                                     if len(comps) > len(live) else "") + ":")
    for c in live:
        log(f"  {c['canonical_name']:<40} {c['hosting']}")
    log(f"\nReport: {result['report']}")
    if args.json:
        print(json.dumps(json.loads((out / "components.json").read_text()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
