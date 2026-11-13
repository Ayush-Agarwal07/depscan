"""Run the whole pipeline on one repository: scan -> prepare -> classify -> merge -> report.

Output layout (<out>):
    report.md          human-readable inventory (start here)
    components.json    machine-readable inventory (schema: docs/OUTPUT.md)
    run_log.json       what ran: mode, provider, model, prompt hash, tokens, cost, timings
    work/              intermediate files (scan results, LLM inputs/answers) for debugging
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from depscan import __version__, classify, merge, prepare, report, scan

MODES = ("static", "llm_only", "hybrid")


class DepscanError(Exception):
    """A user-facing problem (bad path, provider unavailable) — printed without a traceback."""


def default_cache_dir() -> Path:
    if os.getenv("DEPSCAN_CACHE_DIR"):
        return Path(os.environ["DEPSCAN_CACHE_DIR"])
    base = Path(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "depscan"


def resolve_provider(mode: str, llm: str) -> tuple[str, str | None, str]:
    """-> (effective mode, provider name or None, note for the user)."""
    if mode == "static" or llm == "none":
        return "static", None, "static mode: no LLM calls"
    if llm == "auto":
        name = classify.auto_provider()
        if name is None:
            if mode == "llm_only":
                raise DepscanError("llm-only mode needs an LLM, but none is available "
                                   "(no ANTHROPIC_API_KEY, no `claude` CLI, no local Ollama). See README: Providers.")
            return "static", None, ("no LLM available (no ANTHROPIC_API_KEY, no `claude` CLI, no local Ollama) — "
                                    "fell back to static mode; unclear calls are skipped")
        return mode, name, f"LLM provider: {name} (auto-detected)"
    ok, why = classify.provider_available(llm)
    if not ok:
        raise DepscanError(f"--llm {llm} is not usable: {why}")
    return mode, llm, f"LLM provider: {llm}"


def run(repo: Path, out: Path, mode: str = "hybrid", llm: str = "auto", model: str | None = None,
        cache_dir: Path | None = None, workers: int = 4, installed_versions: bool = False,
        dry_run: bool = False, log=print) -> dict:
    repo, out = Path(repo).resolve(), Path(out).resolve()
    if not repo.is_dir():
        raise DepscanError(f"not a directory: {repo}")
    if mode not in MODES:
        raise DepscanError(f"mode must be one of {MODES}")
    mode, provider_name, note = resolve_provider(mode, llm)
    cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
    work = out / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    t = [time.monotonic()]

    log(f"[1/4] scanning {repo} ...")
    meta = scan.run(repo, work / "scan")
    t.append(time.monotonic())
    log(f"      {meta['files_scanned']} Python files, {meta['call_sites']} call sites -> "
        f"{meta['counts']['known_sdk']} SDK calls, {meta['counts']['unclear']} unclear"
        + (f", {len(meta['parse_failures'])} files failed to parse" if meta["parse_failures"] else ""))

    log(f"[2/4] routing ({mode}) ...")
    stats = prepare.run(repo, work, mode)
    t.append(time.monotonic())
    n_llm = stats["llm_call_inputs"] + stats["llm_package_inputs"]
    log(f"      {stats['static_resolved']} resolved statically, {stats['folded']} inbound-framework calls set aside, "
        f"{n_llm} questions for the LLM")

    provider = None
    if mode == "static":
        log(f"[3/4] {note}")
        (work / "llm_results.json").write_text("[]\n")
        cls_stats: dict = {}
    else:
        provider = classify.make_provider(provider_name, model)
        log(f"[3/4] {note}, model {provider.model}; cache {cache_dir}")
        if dry_run:
            log(f"      dry run: would send {n_llm} questions (code excerpts from this repo) to {provider_name}; "
                f"see {work / 'llm_inputs.json'}. Nothing was sent.")
            return {"dry_run": True, "mode": mode, "provider": provider_name, "model": provider.model,
                    "llm_questions": n_llm, "inputs": str(work / "llm_inputs.json")}
        classify.WORKERS = workers
        cls_stats = classify.classify_dir(work, cache_dir, provider)
        log(f"      {cls_stats['entries']} answers ({cls_stats['api_calls']} new calls, {cls_stats['cache_hits']} cached), "
            f"{cls_stats['invalid']} invalid")
    t.append(time.monotonic())

    log("[4/4] merging ...")
    doc = merge.run(repo, work, installed_versions=installed_versions)
    t.append(time.monotonic())

    run_log = {
        "depscan_version": __version__,
        "repo": repo.name, "mode": mode, "requested_llm": llm,
        "provider": provider_name, "model": provider.model if provider else None,
        "prompt_sha256": classify.PROMPT_SHA256 if provider else None,
        "llm_questions": n_llm,
        "api_calls": cls_stats.get("api_calls", 0), "cache_hits": cls_stats.get("cache_hits", 0),
        "invalid_answers": cls_stats.get("invalid", 0),
        "tokens": cls_stats.get("tokens_fresh", {}), "tokens_cold_run": cls_stats.get("tokens_all", {}),
        "cost_usd": cls_stats.get("cost_usd_fresh", 0.0), "cost_usd_cold_run": cls_stats.get("cost_usd_all", 0.0),
        "seconds": {"scan": round(t[1] - t[0], 1), "prepare": round(t[2] - t[1], 1),
                    "classify": round(t[3] - t[2], 1), "merge": round(t[4] - t[3], 1), "total": round(t[4] - t[0], 1)},
        "scan": {k: meta[k] for k in ("files_scanned", "call_sites", "counts", "dependency_files",
                                      "import_roots", "renames", "exclude_patterns", "skip")},
        "parse_failures": meta["parse_failures"],
        "components": len(doc["components"]),
        "installed_versions_read": installed_versions,
    }
    shutil.copyfile(work / "components.json", out / "components.json")
    (out / "run_log.json").write_text(json.dumps(run_log, indent=2) + "\n")
    (out / "report.md").write_text(report.render(doc, run_log))
    return {"components": doc["components"], "run_log": run_log, "report": str(out / "report.md")}


def tool_hash() -> str:
    """Hash of depscan's own source — lets benchmark runs prove which code produced them."""
    src = sorted(Path(__file__).parent.glob("*.py"))
    return hashlib.sha256(b"".join(p.name.encode() + b"\0" + p.read_bytes() for p in src)).hexdigest()
