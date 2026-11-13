"""Validate benchmark/labels/<repo>.json against labels/schema.json, plus semantic checks.

    python3 benchmark/validate_labels.py benchmark/labels/<repo>.json [...]   # one or more files
    python3 benchmark/validate_labels.py --all                               # every labels/*.json

Stdlib only (no jsonschema dependency): implements the keywords schema.json uses — type,
required, properties, additionalProperties:false, items, enum, pattern, minLength,
minItems, maxItems, minimum, maximum. Semantic checks: evidence/ruled_out paths exist and
cited line numbers are inside the file, canonical names are unique, repo name matches.
Exit code 1 on any failure.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "labels" / "schema.json").read_text())
TYPES = {"object": dict, "array": list, "string": str, "number": (int, float), "boolean": bool, "null": type(None)}


def check(node: object, schema: dict, path: str, errors: list[str]) -> None:
    types = schema.get("type")
    if types is not None:
        allowed = [types] if isinstance(types, str) else types
        ok = any(
            isinstance(node, TYPES[t]) and not (t == "number" and isinstance(node, bool))
            for t in allowed
        )
        if not ok:
            errors.append(f"{path}: expected {allowed}, got {type(node).__name__}")
            return
    if "enum" in schema and node not in schema["enum"]:
        errors.append(f"{path}: {node!r} not in {schema['enum']}")
    if isinstance(node, str):
        if len(node) < schema.get("minLength", 0):
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], node):
            errors.append(f"{path}: {node!r} does not match {schema['pattern']}")
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        if "minimum" in schema and node < schema["minimum"]:
            errors.append(f"{path}: {node} < {schema['minimum']}")
        if "maximum" in schema and node > schema["maximum"]:
            errors.append(f"{path}: {node} > {schema['maximum']}")
    if isinstance(node, dict):
        for key in schema.get("required", []):
            if key not in node:
                errors.append(f"{path}: missing required '{key}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in node:
                if key not in props:
                    errors.append(f"{path}: unexpected field '{key}'")
        for key, sub in props.items():
            if key in node:
                check(node[key], sub, f"{path}.{key}", errors)
    if isinstance(node, list):
        if len(node) < schema.get("minItems", 0):
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(node) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, item in enumerate(node):
                check(item, schema["items"], f"{path}[{i}]", errors)


def location_ok(repo: Path, location: str, need_line: bool) -> str | None:
    m = re.fullmatch(r"(.+?)(?::(\d+))?", location)
    rel, line = m.group(1), m.group(2)
    if need_line and line is None:
        return f"{location}: no line number"
    target = repo / rel
    if not target.exists():
        return f"{location}: file not found under {repo}"
    if line is not None:
        if target.is_dir():
            return f"{location}: is a directory"
        n = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        if not 1 <= int(line) <= n:
            return f"{location}: line {line} outside 1..{n}"
    return None


def validate(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    errors: list[str] = []
    check(data, SCHEMA, "$", errors)
    if errors:
        return errors
    if data["repo"] != path.stem:
        errors.append(f"$.repo {data['repo']!r} != file name {path.stem!r}")
    repo = Path(data["repo_path"])
    if not repo.is_absolute():
        repo = HERE.parent / repo  # relative paths are relative to the depscan checkout
    if not repo.is_dir():
        return errors + [f"$.repo_path {repo} is not a directory"]
    names = [c["canonical_name"] for c in data["components"]]
    errors += [f"duplicate canonical_name {n!r}" for n in sorted({n for n in names if names.count(n) > 1})]
    for i, c in enumerate(data["components"]):
        for ev in c["evidence"]:
            if (msg := location_ok(repo, ev["location"], need_line=True)):
                errors.append(f"components[{i}] {c['canonical_name']}: {msg}")
    for i, r in enumerate(data["ruled_out"]):
        if (msg := location_ok(repo, r["location"], need_line=False)):
            errors.append(f"ruled_out[{i}]: {msg}")
    return errors


def main() -> None:
    files = sorted((HERE / "labels").glob("*.json")) if "--all" in sys.argv else [Path(a) for a in sys.argv[1:]]
    files = [f for f in files if f.name != "schema.json"]
    if not files:
        sys.exit("no labels files given")
    failed = 0
    for f in files:
        errors = validate(f)
        data = json.loads(f.read_text()) if not errors or not errors[0].startswith("invalid JSON") else {}
        summary = (f"{len(data.get('components', []))} components, {len(data.get('ruled_out', []))} ruled_out, "
                   f"{len(data.get('out_of_scope', []))} out_of_scope") if data else ""
        print(f"{'OK  ' if not errors else 'FAIL'} {f.name}  {summary}")
        for e in errors:
            print(f"     - {e}")
        failed += bool(errors)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
