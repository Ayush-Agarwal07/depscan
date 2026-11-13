"""Run depscan on every benchmark repo x mode. Resumable: a repo x mode already run with the
current depscan source (same tool hash) is skipped, so an interrupted run just continues.

    python benchmark/run.py                         # all repos, hybrid only
    python benchmark/run.py --modes static,hybrid,llm_only --set heldout
    python benchmark/run.py --budget-min 25         # stop starting new jobs after 25 min

Outputs: benchmark/runs/<repo>/<mode>/{components.json, report.md, run_log.json, work/}.
LLM answers are cached in benchmark/cache/ (shared across modes and runs).
Provider: the `claude` CLI (Claude Opus 5.5 on the user's Claude login) unless --llm says otherwise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))  # run against this checkout, installed or not

from depscan import pipeline  # noqa: E402


def current_sha(path: str) -> str | None:
    r = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True)
    top = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and top.stdout.strip() == str(Path(path).resolve()) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["dev", "heldout", "all"], default="all")
    ap.add_argument("--modes", default="hybrid")
    ap.add_argument("--repos", help="comma-separated subset of repo names")
    ap.add_argument("--llm", default="claude-cli")
    ap.add_argument("--budget-min", type=float, default=0, help="0 = no budget")
    args = ap.parse_args()

    repos = json.loads((HERE / "repos.json").read_text())
    if args.set != "all":
        repos = [r for r in repos if r["set"] == args.set]
    if args.repos:
        wanted = set(args.repos.split(","))
        repos = [r for r in repos if r["name"] in wanted]
    tool = pipeline.tool_hash()
    deadline = time.monotonic() + args.budget_min * 60 if args.budget_min else None
    for mode in args.modes.split(","):
        for r in repos:
            out = HERE / "runs" / r["name"] / mode
            log_file = out / "run_log.json"
            if log_file.exists() and json.loads(log_file.read_text()).get("tool_hash") == tool:
                print(f"skip  {r['name']} {mode} (already run with this tool version)")
                continue
            if deadline and time.monotonic() > deadline:
                print("budget used up; rerun to continue")
                raise SystemExit(3)
            path = HERE.parent / r["path"]  # paths in repos.json are relative to the depscan checkout
            if not path.is_dir():
                raise SystemExit(f"{path} missing — run: python benchmark/fetch_repos.py")
            if r["sha"] and current_sha(str(path)) != r["sha"]:
                raise SystemExit(f"{r['name']} is not at its pinned commit {r['sha'][:10]}; check out that commit first")
            t0 = time.monotonic()
            res = pipeline.run(path, out, mode=mode, llm=args.llm, cache_dir=HERE / "cache", log=lambda m: None)
            log = res["run_log"] | {"tool_hash": tool, "benchmark_set": r["set"]}
            log_file.write_text(json.dumps(log, indent=2) + "\n")
            print(f"done  {r['name']:<28} {mode:<9} components={log['components']:<3} new_calls={log['api_calls']:<4} "
                  f"cached={log['cache_hits']:<4} invalid={log['invalid_answers']} ({time.monotonic() - t0:.0f}s)")
    print("all done")


if __name__ == "__main__":
    main()
