"""Step 4: merge static resolutions + LLM labels into the component list for one run.

Reads <run_dir>/{static_resolved,llm_results,folded}.json and scan/scan_meta.json; writes
<run_dir>/components.json and summary.md. Deterministic: sorted output, no timestamps.

Versions (no single "version" — they mean different things):
- package_version: exact pin of the client package (lockfile, or `==`), for SDK-derived evidence
- declared_range: the declared spec when it isn't an exact pin
- installed_version: importlib.metadata in the repo's own .venv, if it has one
- api_version: version_hint the LLM found literally in the code (URL path / header)
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from depscan import aliases

EXACT = re.compile(r"^(==\s*)?\d[\w.+!-]*$")


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def repo_versions(root: Path, dists: list[str]) -> dict[str, str]:
    python = root / ".venv" / "bin" / "python"
    if not python.exists():
        return {d: "unknown (no repo venv)" for d in dists} | {"__sqlite__": "unknown (no repo venv)"}
    code = (
        "import importlib.metadata as m, json, sqlite3, sys\n"
        "out = {'__sqlite__': sqlite3.sqlite_version}\n"
        "for d in sys.argv[1:]:\n"
        "    try: out[d] = m.version(d)\n"
        "    except m.PackageNotFoundError: out[d] = 'not installed'\n"
        "print(json.dumps(out))\n"
    )
    run = subprocess.run([str(python), "-c", code, *dists], capture_output=True, text=True)
    if run.returncode != 0:
        return {d: "unknown (repo venv failed)" for d in dists} | {"__sqlite__": "unknown (repo venv failed)"}
    return json.loads(run.stdout)


def evidence(file: str, line: int, callee: str | None, found_by: str, excluded_by: str | None,
             confidence: float | None, pkg: dict | None, scan_kind: str | None = None) -> dict:
    return {
        "location": f"{file}:{line}", "callee": callee, "found_by": found_by, "scan_kind": scan_kind,
        "excluded_by": excluded_by, "confidence": confidence, "_pkg": pkg,
    }


# Providers whose names cover many unrelated products: never merged by provider alone.
MULTI_PRODUCT = {"aws", "gcp", "azure", "google", "microsoft", "web"}


def _dirs(items: list[dict]) -> set[str]:
    return {e["location"].rsplit(":", 1)[0].rpartition("/")[0] for e in items}


def consolidate(groups: dict, hosting: dict, targets: dict, api_versions: dict) -> dict[str, list[str]]:
    """Merge names that are one service split per endpoint (acme/events + acme/orders ...).

    Two names merge when they share a provider (not a multi-product one), have the same majority
    hosting, and have evidence in a common directory. The merged component keeps the name with the
    most evidence (ties: alphabetical). Mutates the dicts in place; returns {kept_name: [all names]}.
    """
    def major(name: str) -> str:
        return sorted(hosting[name].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    names = sorted(groups)
    parent = {n: n for n in names}

    def find(n: str) -> str:
        while parent[n] != n:
            n = parent[n]
        return n

    for i, a in enumerate(names):
        prov = a.split("/")[0]
        if prov in MULTI_PRODUCT:
            continue
        for b in names[i + 1:]:
            if b.split("/")[0] == prov and major(a) == major(b) and _dirs(groups[a]) & _dirs(groups[b]):
                parent[find(b)] = find(a)
    clusters: dict[str, list[str]] = defaultdict(list)
    for n in names:
        clusters[find(n)].append(n)
    merged = {}
    for members in clusters.values():
        if len(members) == 1:
            continue
        keep = sorted(members, key=lambda n: (-len(groups[n]), n))[0]
        for n in members:
            if n == keep:
                continue
            groups[keep].extend(groups.pop(n))
            hosting[keep].update(hosting.pop(n))
            targets[keep].update(targets.pop(n, Counter()))
            api_versions[keep].update(api_versions.pop(n, Counter()))
        merged[keep] = sorted(members)
    return merged


def run(root: Path, run_dir: Path, installed_versions: bool = False) -> dict:
    """Merge static + LLM results in `run_dir` into components.json and summary.md; return the
    components document. `installed_versions` runs the target repo's own .venv Python to read
    installed package versions — off by default because it executes code from the scanned repo."""
    root, run_dir = Path(root).resolve(), Path(run_dir).resolve()
    static = load(run_dir / "static_resolved.json", [])
    results = load(run_dir / "llm_results.json", [])
    folded = load(run_dir / "folded.json", {"call_sites": 0, "packages": {}, "evidence": []})
    meta = load(run_dir / "scan" / "scan_meta.json", {})
    mode = load(run_dir / "prepare_stats.json", {}).get("mode")

    groups: dict[str, list[dict]] = defaultdict(list)
    hosting: dict[str, Counter] = defaultdict(Counter)
    targets: dict[str, Counter] = defaultdict(Counter)
    api_versions: dict[str, Counter] = defaultdict(Counter)

    def pkg_of(d: dict) -> dict | None:
        if not d.get("dist"):
            return None
        return {"dist": d["dist"], "version": d["version"], "version_source": d["version_source"]}

    for s in static:
        name = aliases.normalize_name(s["canonical_name"])
        groups[name].append(evidence(s["file"], s["line"], s["callee"], s["found_by"], s["excluded_by"], None,
                                     pkg_of(s), "known_sdk"))
        hosting[name][s["hosting"] or "unknown"] += 1

    for r in results:
        if not (r["valid"] and r["is_external_api"]):
            continue
        name = aliases.normalize_name(r["canonical_name"])
        sdk_backed = r["kind"] == "package" or r["scan_class"] == "known_sdk"
        pkg = pkg_of(r) if sdk_backed else None
        if r["kind"] == "package":
            items = [evidence(c["file"], c["line"], c["callee"], "llm-package", c["excluded_by"], r["confidence"],
                              pkg, "package") for c in r["call_sites"]]
        else:
            items = [evidence(r["file"], r["line"], r["callee"], "llm-call", r["excluded_by"], r["confidence"],
                              pkg, r["scan_kind"])]
        groups[name].extend(items)
        hosting[name][r["hosting"]] += len(items)
        if r["default_target"]:
            targets[name][r["default_target"]] += 1
        if r["version_hint"]:
            api_versions[name][r["version_hint"]] += 1

    merged_from = consolidate(groups, hosting, targets, api_versions)

    dists = sorted({e["_pkg"]["dist"] for items in groups.values() for e in items if e["_pkg"]})
    installed = repo_versions(root, dists) if installed_versions else {}

    components, conflicts = [], []
    for name in sorted(groups):
        items = sorted(groups[name], key=lambda e: (e["location"].rsplit(":", 1)[0],
                                                    int(e["location"].rsplit(":", 1)[1]), e["callee"] or "", e["found_by"]))
        host_counts = hosting[name]
        host = sorted(host_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        if len(host_counts) > 1:
            conflicts.append({"canonical_name": name, "hosting_votes": dict(sorted(host_counts.items()))})
        pkgs = Counter(e["_pkg"]["dist"] for e in items if e["_pkg"])
        pkg_info = None
        if pkgs:
            dist = sorted(pkgs.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            pkg_info = next(e["_pkg"] for e in items if e["_pkg"] and e["_pkg"]["dist"] == dist)
        version = pkg_info["version"] if pkg_info else None
        exact = bool(version) and (pkg_info["version_source"].startswith("lockfile") or bool(EXACT.match(version)))
        sqlite_backed = any((e["callee"] or "").startswith("sqlite3.") for e in items)
        api = sorted(api_versions[name].items(), key=lambda kv: (-kv[1], kv[0]))
        confs = [e["confidence"] for e in items if e["confidence"] is not None]
        components.append({
            "canonical_name": name,
            "hosting": host,
            "default_target": sorted(targets[name].items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if targets[name] else None,
            "package_name": pkg_info["dist"] if pkg_info else None,
            "package_version": version.lstrip("= ") if exact else None,
            "declared_range": version if (version and not exact and version != "unknown") else None,
            "installed_version": installed.get("__sqlite__") if sqlite_backed and not pkg_info
            else (installed.get(pkg_info["dist"]) if pkg_info else None),
            "api_version": api[0][0] if api else None,
            "api_versions_seen": [v for v, _ in api],
            "version_source": (
                f"package: {pkg_info['version_source']}" if pkg_info else "package: none (no client package)"
            ) + ("; api: literal in code" if api else "; api: none in code"),
            "excluded": all(e["excluded_by"] for e in items),
            "found_by": dict(sorted(Counter(e["found_by"] for e in items).items())),
            "min_confidence": min(confs) if confs else None,
            "merged_from": merged_from.get(name, []),
            "evidence": [{k: v for k, v in e.items() if k != "_pkg"} for e in items],
        })

    out = {
        "mode": mode,
        "repo": root.name,  # name only: outputs get shared, absolute paths leak usernames
        "components": components,
        "inbound": folded,
        "hosting_conflicts": conflicts,
        "renames_detected": meta.get("renames", {}),
        "exclude_patterns": meta.get("exclude_patterns", []),
    }
    (run_dir / "components.json").write_text(json.dumps(out, indent=2) + "\n")

    lines = [
        f"# Components — {root.name} ({mode})", "",
        f"- {len(components)} components "
        f"({sum(c['hosting'] == 'cloud' for c in components)} cloud, "
        f"{sum(c['hosting'] == 'self-hosted' for c in components)} self-hosted, "
        f"{sum(c['hosting'] == 'unknown' for c in components)} unknown hosting)",
        f"- inbound framework call sites folded: {folded.get('call_sites', 0)} {folded.get('packages', {})}",
        f"- hosting conflicts: {len(conflicts)}", "",
        "| component | hosting | package | pin | api | evidence | found by | excluded |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in components:
        lines.append(f"| `{c['canonical_name']}` | {c['hosting']} | {c['package_name'] or '-'} | "
                     f"{c['package_version'] or '-'} | {c['api_version'] or '-'} | {len(c['evidence'])} | "
                     f"{', '.join(f'{k} {v}' for k, v in c['found_by'].items())} | {'yes' if c['excluded'] else ''} |")
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    return out
