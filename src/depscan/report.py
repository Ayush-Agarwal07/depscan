"""Render components.json as a short, human-readable Markdown report."""

from __future__ import annotations

FOUND_BY = {
    "static-alias": "known SDK",
    "static-fallback": "declared package",
    "llm-call": "LLM (call site)",
    "llm-package": "LLM (package)",
}


def _version(c: dict) -> str:
    parts = []
    if c.get("package_version"):
        parts.append(f"{c['package_name']}=={c['package_version']}")
    elif c.get("declared_range"):
        parts.append(f"{c['package_name']} {c['declared_range']}")
    if c.get("api_version"):
        parts.append(f"API {c['api_version']}")
    if c.get("installed_version") and not str(c["installed_version"]).startswith(("unknown", "not installed")):
        parts.append(f"installed {c['installed_version']}")
    return "; ".join(parts) or "—"


def _where(c: dict, n: int = 3) -> str:
    ev = sorted(c["evidence"], key=lambda e: (bool(e.get("excluded_by")), e["location"]))
    locs = [f"`{e['location']}`" for e in ev[:n]]
    more = len(ev) - n
    return ", ".join(locs) + (f" (+{more} more)" if more > 0 else "")


def _how(c: dict) -> str:
    kinds = sorted({FOUND_BY.get(k, k) for k in c.get("found_by", {})})
    conf = c.get("min_confidence")
    return ", ".join(kinds) + (f" · conf ≥ {conf:.2f}" if isinstance(conf, (int, float)) else "")


def _row(c: dict) -> str:
    target = f" → {c['default_target']}" if c.get("default_target") else ""
    others = [n for n in c.get("merged_from", []) if n != c["canonical_name"]]
    aka = f"<br>also named: {', '.join(f'`{n}`' for n in others)}" if others else ""
    return (f"| `{c['canonical_name']}`{target}{aka} | {c['hosting']} | {_version(c)} | {_where(c)} | {_how(c)} |")


def render(doc: dict, run_log: dict) -> str:
    comps = doc["components"]
    live = [c for c in comps if not c.get("excluded")]
    excluded = [c for c in comps if c.get("excluded")]
    hosting = {h: sum(c["hosting"] == h for c in live) for h in ("cloud", "self-hosted", "unknown")}
    llm = (f"{run_log['provider']} / {run_log['model']}" if run_log.get("provider") else "none (static mode)")
    head = "| component | hosting | version | used at | found by |\n|---|---|---|---|---|"
    lines = [
        f"# External dependencies — {run_log['repo']}", "",
        f"**{len(live)} external components** ({hosting['cloud']} cloud, {hosting['self-hosted']} self-hosted"
        + (f", {hosting['unknown']} unknown" if hosting["unknown"] else "") + ")"
        + (f", plus {len(excluded)} only in excluded code" if excluded else "") + ".", "",
        f"Mode `{run_log['mode']}` · LLM {llm} · {run_log['scan']['files_scanned']} Python files · "
        f"{run_log['api_calls']} LLM calls ({run_log['cache_hits']} cached) · {run_log['seconds']['total']} s", "",
        "## Components", "", head, *(_row(c) for c in live), "",
    ]
    if excluded:
        lines += ["## Only in excluded code", "",
                  f"Every use is under a path excluded in pyproject.toml ({', '.join(doc.get('exclude_patterns', []))}) — "
                  "e.g. deprecated code or tests.", "", head, *(_row(c) for c in excluded), ""]
    inbound = doc.get("inbound") or {}
    if inbound.get("call_sites"):
        pk = ", ".join(inbound.get("packages", {}))
        lines += ["## Not counted", "", f"- Inbound web frameworks serving this app ({pk}, "
                  f"{inbound['call_sites']} call sites): these serve requests; they aren't external services.", ""]
    if doc.get("hosting_conflicts"):
        lines += ["## Hosting conflicts", "",
                  *(f"- `{h['canonical_name']}`: votes {h['hosting_votes']}" for h in doc["hosting_conflicts"]), ""]
    if run_log.get("parse_failures"):
        lines += ["## Files that could not be parsed", "",
                  "Their calls are missing from this report. A syntax error here usually means the code uses newer "
                  "Python syntax than the interpreter running depscan — run it with a newer Python "
                  "(e.g. `uvx --python 3.14 depscan ...`).", "", *(f"- {p}" for p in run_log["parse_failures"]), ""]
    lines += [
        "## How to read this", "",
        "- **found by**: *known SDK* = a call into a well-known client library (no LLM); *LLM (call site)* / "
        "*LLM (package)* = an LLM read the surrounding code and named the service; *declared package* = static "
        "mode's guess from a dependency name. Lower confidence deserves a look.",
        "- **version**: an exact pin from a lockfile or `==` requirement, else the declared range; *API vN* is a "
        "version written in the code (URL path or header).",
        "- **Limits**: only Python code is scanned; code that ships but never runs (e.g. a legacy folder) is still "
        "reported unless excluded in pyproject.toml; names an LLM gave to one service are merged when they share a "
        "provider, hosting and directory (shown as *also named*), but a service can still appear twice.",
        "- Full detail per component (every call site): `components.json`. What ran: `run_log.json`.", "",
    ]
    return "\n".join(lines)
