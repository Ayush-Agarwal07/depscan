"""Step 2: route scanner candidates for one mode and build the LLM inputs.

Reads <run_dir>/scan/{known_sdk,unclear,scan_meta}.json. Writes into <run_dir>:
- static_resolved.json  calls named without an LLM (alias table; static mode's fallback names)
- llm_inputs.json       entries for classify.py: kind "call" (one call site) or "package"
                        (one third-party package, with sample call sites)
- folded.json           inbound web-framework calls (not components)

Modes:
- static    known SDK calls only: alias-table name, else `<package>/sdk`; unclear calls dropped.
- llm_only  every candidate call site (known SDK + unclear) goes to the LLM, one call each.
- hybrid    alias-table SDK calls resolved statically; other declared packages labelled once
            per package by the LLM; unclear calls (raw HTTP, wrappers, dispatch, stdlib clients,
            undeclared packages) labelled per call by the LLM.
In every mode, `{self.<attr>}` placeholders in URLs are traced to their defaults
(self-assignments -> constructor calls, keyword and positional -> settings-field defaults).
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path

from depscan import aliases, scan

MODES = ("static", "llm_only", "hybrid")
MAX_TRACE = 8
PACKAGE_SAMPLES = 3


# --------------------------------------------------------------------------- repo index
def index_repo(root: Path) -> tuple[list, dict, dict, dict]:
    scan.ROOT = root
    scan.read_scan_config()
    deps = scan.read_dependencies()
    files, _ = scan.load_files()
    local_tops = {fi.mod.split(".")[0] for fi in files}
    scan.LOCAL_RENAMES.clear()
    scan.LOCAL_RENAMES.update(scan.detect_renames(files, deps, local_tops))
    defs: dict = {}
    for fi in files:
        scan.collect_imports(fi)
        scan.collect_defs(fi, defs)
    return files, {fi.mod: fi for fi in files}, {fi.rel: fi for fi in files}, defs


def resolve_name(fi, func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        if func.id in fi.aliases:
            return fi.aliases[func.id]
        return f"{fi.mod}.{func.id}" if func.id in fi.module_defs else None
    if isinstance(func, ast.Attribute):
        base = resolve_name(fi, func.value)
        return f"{base}.{func.attr}" if base else None
    return None


def enclosing_class(fi, line: int) -> ast.ClassDef | None:
    best = None
    for node in ast.walk(fi.tree):
        if isinstance(node, ast.ClassDef) and node.lineno <= line <= (node.end_lineno or 0):
            if best is None or node.lineno > best.lineno:
                best = node
    return best


def _qualname(fi, cls: ast.ClassDef) -> str:
    """Dotted qualname of a (possibly nested) class inside its module."""
    path: list[str] = []

    def walk(body: list, prefix: list[str]) -> bool:
        for node in body:
            if isinstance(node, ast.ClassDef):
                if node is cls:
                    path.extend(prefix + [node.name])
                    return True
                if walk(node.body, prefix + [node.name]):
                    return True
        return False

    walk(fi.tree.body, [])
    return ".".join([fi.mod, *path])


def _rec(fi, node: ast.AST, kind: str) -> dict:
    return {"location": f"{fi.rel}:{node.lineno}", "kind": kind, "code": fi.lines[node.lineno - 1].strip()}


def trace_attr(entry: dict, attr: str, files: list, by_rel: dict, by_mod: dict, defs: dict) -> list[dict]:
    """Where `self.<attr>` gets its value: assignments in the class, the constructor calls that
    feed the parameter it comes from (keyword or positional), and settings-field defaults."""
    fi = by_rel.get(entry["file"])
    cls = enclosing_class(fi, entry["line"]) if fi else None
    if cls is None:
        return []
    out: list[dict] = []
    params: set[str] = set()
    init = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
    init_params = [a.arg for a in init.args.args[1:]] if init else []
    init_kwonly = [a.arg for a in init.args.kwonlyargs] if init else []
    for node in ast.walk(cls):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Attribute) and t.attr == attr for t in targets) and node.value is not None:
                out.append(_rec(fi, node, "self_assign"))
                params |= {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
    params &= set(init_params) | set(init_kwonly)
    if not params:
        return out[:MAX_TRACE]

    qual = _qualname(fi, cls)
    fields: set[str] = set()
    for other in files:
        for node in ast.walk(other.tree):
            if not isinstance(node, ast.Call):
                continue
            callee = resolve_name(other, node.func)
            if callee is None or scan.canonical_local(callee, by_mod, defs) != qual:
                continue
            for kw in node.keywords:
                if kw.arg in params:
                    out.append(_rec(other, kw.value, "constructor_kwarg"))
                    if isinstance(kw.value, ast.Attribute):
                        fields.add(kw.value.attr)
            for i, arg in enumerate(node.args):
                if i < len(init_params) and init_params[i] in params:
                    out.append(_rec(other, arg, "constructor_positional"))
                    if isinstance(arg, ast.Attribute):
                        fields.add(arg.attr)
    package = fi.mod.split(".")[0]
    for other in files:
        if not fields or other.mod.split(".")[0] != package:
            continue
        for node in ast.walk(other.tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and node.target.id in fields and node.value is not None:
                out.append(_rec(other, node, "field_default"))
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in fields for t in node.targets):
                out.append(_rec(other, node, "field_default"))
            elif isinstance(node, ast.keyword) and node.arg in fields:
                out.append(_rec(other, node.value, "field_kwarg"))
    seen, uniq = set(), []
    for r in sorted(out, key=lambda r: (r["location"].rsplit(":", 1)[0], int(r["location"].rsplit(":", 1)[1]), r["kind"])):
        if (r["location"], r["kind"]) not in seen:
            seen.add((r["location"], r["kind"]))
            uniq.append(r)
    return uniq[:MAX_TRACE]


# --------------------------------------------------------------------------- contexts
def call_context(e: dict) -> str:
    parts = [
        "input kind: call",
        f"file: {e['file']}",
        f"line: {e['line']}",
        f"raw callee: {e['raw_callee']}",
        f"resolved callee: {e['callee']}",
        f"static-analysis note: {e['reason']}",
        f"url expression: {e['url']}",
        f"arguments: {json.dumps(e['args'])}",
        "",
        "--- surrounding code ---",
        e["context"],
        "",
        "--- file imports ---",
        "\n".join(e["file_imports"]) or "(none)",
    ]
    if e.get("called_function_source"):
        parts += ["", f"--- source of {e['called_function']} ---", e["called_function_source"]]
    for attr, recs in sorted((e.get("traces") or {}).items()):
        if recs:
            parts += ["", f"--- where self.{attr}'s value comes from ---"]
            parts += [f"{r['location']}: {r['code']}" for r in recs]
    return "\n".join(parts)


def package_context(top: str, entries: list[dict]) -> str:
    first = entries[0]
    samples = []
    seen_files = set()
    for e in entries:
        if e["file"] not in seen_files:
            seen_files.add(e["file"])
            samples.append(e)
        if len(samples) == PACKAGE_SAMPLES:
            break
    callees = sorted({e["callee"] for e in entries})
    parts = [
        "input kind: package",
        f"package (top-level import): {top}",
        f"distribution: {first['dist']}  declared version: {first['version']} ({first['version_source']})",
        f"call sites in repo: {len(entries)} across {len({e['file'] for e in entries})} files",
        "distinct callees (up to 15): " + ", ".join(callees[:15]),
    ]
    for e in samples:
        parts += ["", f"--- sample call site {e['file']}:{e['line']} ---", e["context"],
                  "--- that file's imports ---", "\n".join(e["file_imports"]) or "(none)"]
    return "\n".join(parts)


# --------------------------------------------------------------------------- routing
def static_entry(e: dict, name: str, hosting: str | None, found_by: str) -> dict:
    return {
        "file": e["file"], "line": e["line"], "callee": e["callee"], "excluded_by": e["excluded_by"],
        "package": e["package"], "dist": e["dist"], "version": e["version"],
        "version_source": e["version_source"], "canonical_name": name, "hosting": hosting,
        "found_by": found_by,
    }


def endpoint_overridden_packages(known: list[dict]) -> set[str]:
    """Aliased packages whose client is constructed with an explicit endpoint (base_url=…):
    the alias assumes the default endpoint, so those packages go to the LLM instead (D-29)."""
    out = set()
    for e in known:
        is_constructor = "()" not in (e["callee"] or "")
        if is_constructor and any(a.split("=", 1)[0] in aliases.ENDPOINT_KWARGS for a in e["args"] if "=" in a):
            out.add(e["package"])
    return out


def run(root: Path, run_dir: Path, mode: str) -> dict:
    """Route scan results for `mode`; write llm_inputs.json, static_resolved.json, folded.json
    and prepare_stats.json into `run_dir` (which must contain scan/). Returns the stats."""
    root, run_dir = Path(root).resolve(), Path(run_dir).resolve()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    known = json.loads((run_dir / "scan" / "known_sdk.json").read_text())
    unclear = json.loads((run_dir / "scan" / "unclear.json").read_text())
    files, by_mod, by_rel, defs = index_repo(root)

    def inbound(e: dict) -> bool:
        return (e["callee"] or "").split(".")[0] in scan.INBOUND_SERVER_PACKAGES

    folded = [e for e in known + unclear if inbound(e)] if mode != "llm_only" else []
    folded_ids = {id(e) for e in folded}
    known = [e for e in known if id(e) not in folded_ids]
    unclear = [e for e in unclear if id(e) not in folded_ids]

    for e in unclear + known:
        attrs = sorted(set(re.findall(r"\{self\.([A-Za-z_]\w*)", e.get("url") or "")))
        e["traces"] = {a: trace_attr(e, a, files, by_rel, by_mod, defs) for a in attrs}

    static_resolved: list[dict] = []
    calls: list[dict] = []
    packages: dict[str, list[dict]] = defaultdict(list)
    overridden = endpoint_overridden_packages(known)

    if mode == "static":
        for e in known:
            hit = aliases.sdk_component(e["package"], e["callee"], e["args"])
            if hit:
                static_resolved.append(static_entry(e, hit[0], hit[1], "static-alias"))
            else:
                static_resolved.append(static_entry(e, f"{e['package'].lower()}/sdk", None, "static-fallback"))
    elif mode == "llm_only":
        calls = known + unclear
    else:  # hybrid
        for e in known:
            hit = aliases.sdk_component(e["package"], e["callee"], e["args"])
            if hit and e["package"] not in overridden:
                static_resolved.append(static_entry(e, hit[0], hit[1], "static-alias"))
            else:
                packages[e["package"]].append(e)
        calls = unclear

    inputs: list[dict] = []
    seen: dict[str, int] = defaultdict(int)
    for e in sorted(calls, key=lambda e: (e["file"], e["line"], e["raw_callee"])):
        base_id = f"{e['file']}:{e['line']}:{e['raw_callee']}"
        seen[base_id] += 1
        inputs.append({
            "id": base_id if seen[base_id] == 1 else f"{base_id}#{seen[base_id]}",
            "kind": "call",
            "file": e["file"], "line": e["line"], "callee": e["callee"], "raw_callee": e["raw_callee"],
            "package": e.get("package") or (e["callee"] or "").split(".")[0] or None,
            "scan_class": e["class"], "scan_kind": e.get("unclear_kind", "known_sdk"),
            "url": e["url"], "excluded_by": e["excluded_by"],
            "dist": e.get("dist"), "version": e.get("version"), "version_source": e.get("version_source"),
            "traces": e["traces"],
            "llm_context": call_context(e),
        })
    for top, entries in sorted(packages.items()):
        entries = sorted(entries, key=lambda e: (e["file"], e["line"]))
        inputs.append({
            "id": f"package:{top}",
            "kind": "package",
            "file": entries[0]["file"], "line": entries[0]["line"], "callee": None, "raw_callee": None,
            "package": top, "scan_class": "known_sdk", "scan_kind": "package",
            "url": None, "excluded_by": None,
            "dist": entries[0]["dist"], "version": entries[0]["version"],
            "version_source": entries[0]["version_source"],
            "endpoint_override": top in overridden,
            "call_sites": [{"file": e["file"], "line": e["line"], "callee": e["callee"],
                            "excluded_by": e["excluded_by"]} for e in entries],
            "traces": {},
            "llm_context": package_context(top, entries),
        })

    by_pkg: dict[str, int] = defaultdict(int)
    for e in folded:
        by_pkg[(e["callee"] or "").split(".")[0]] += 1
    note = {
        "role": "inbound",
        "packages": dict(sorted(by_pkg.items())),
        "call_sites": len(folded),
        "evidence": [f"{e['file']}:{e['line']}" for e in sorted(folded, key=lambda e: (e["file"], e["line"]))],
    }
    (run_dir / "folded.json").write_text(json.dumps(note, indent=2) + "\n")
    (run_dir / "static_resolved.json").write_text(json.dumps(static_resolved, indent=2) + "\n")
    (run_dir / "llm_inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    stats = {
        "mode": mode,
        "candidates": len(known) + len(unclear) + len(folded),
        "folded": len(folded),
        "static_resolved": len(static_resolved),
        "llm_call_inputs": sum(i["kind"] == "call" for i in inputs),
        "llm_package_inputs": sum(i["kind"] == "package" for i in inputs),
        "llm_package_call_sites": sum(len(i.get("call_sites", [])) for i in inputs),
        "dropped_unclear": len(unclear) if mode == "static" else 0,
        "endpoint_overridden_packages": sorted(overridden),
        "traced_entries": sum(1 for i in inputs if any(i["traces"].values())),
    }
    (run_dir / "prepare_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    return stats
