"""Step 1 — static scan of one Python repository (stdlib only, `ast` based).

Finds every call site, resolves imports/aliases, and sorts calls into: known SDK calls (into a
declared third-party package), unclear calls (raw HTTP, local wrappers around external calls,
dynamically dispatched clients, stdlib network clients, undeclared packages), and ignored.

Target-repo configuration is read from its pyproject.toml, never hard-coded here:
- `[tool.setuptools.packages.find].exclude` and `[tool.depscan].exclude` -> evidence in
  matching paths is flagged `excluded_by` (e.g. deprecated code), still reported;
- `[tool.depscan].skip` -> directories not scanned at all.
"""

from __future__ import annotations

import ast
import builtins
import fnmatch
import json
import os
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path.cwd()  # set by run()
OUT = Path.cwd()   # set by run()
TOOL_DIR = Path(__file__).resolve().parent  # never scan the tool itself
SOURCE_ROOTS: list[Path] = []  # import roots (e.g. src/, backend/); empty -> ROOT only
SKIP_DIRS = {
    ".venv", "venv", "env", "node_modules", ".git", "build", "dist", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".next",
}
EXTRA_SKIP: list[Path] = []  # from [tool.depscan].skip in the target pyproject.toml
EXCLUDE_PATTERNS: list[str] = []  # from setuptools find.exclude + [tool.depscan].exclude
# Filled per run by detect_renames(): a package that imports itself under an old name.
LOCAL_RENAMES: dict[str, str] = {}
# Declared deps that never touch the network: pure local libs, classified `ignored`.
# Deliberately short; anything else is decided downstream (the LLM's package step).
LOCAL_ONLY_PACKAGES = {"pydantic", "rich", "typer", "yaml", "dotenv", "pytest", "mypy", "ruff"}
# Well-known distribution -> import mismatches; the rest goes through dist_import_names().
DIST_TO_IMPORT = {
    "python-dotenv": "dotenv", "pyyaml": "yaml", "beautifulsoup4": "bs4", "pillow": "PIL",
    "scikit-learn": "sklearn", "opencv-python": "cv2", "protobuf": "google",
}
# stdlib network clients (connection constructors); exact resolved callee names.
STDLIB_CLIENTS = {
    "sqlite3.connect", "smtplib.SMTP", "smtplib.SMTP_SSL", "smtplib.LMTP",
    "socket.create_connection", "socket.socket().connect", "socket.socket().connect_ex",
    "ftplib.FTP", "ftplib.FTP_TLS", "imaplib.IMAP4", "imaplib.IMAP4_SSL", "poplib.POP3",
    "poplib.POP3_SSL", "xmlrpc.client.ServerProxy", "telnetlib.Telnet", "asyncio.open_connection",
}
LOCKFILES = ("poetry.lock", "uv.lock", "Pipfile.lock")
RAW_HTTP_EXACT = {
    "urllib.request.urlopen", "urllib.request.Request", "urllib.request.build_opener",
    "urllib.request.urlretrieve", "http.client.HTTPConnection", "http.client.HTTPSConnection",
}
RAW_HTTP_PKGS = {"requests", "httpx", "aiohttp", "urllib3"}
# Inbound web-server frameworks: folded downstream, never make a function a "wrapper".
INBOUND_SERVER_PACKAGES = {
    "fastapi", "uvicorn", "starlette", "flask", "django", "gunicorn", "sanic", "tornado", "quart",
    "litestar",
}
HTTP_VERBS = {"get", "post", "put", "patch", "delete", "head", "request", "stream", "send"}
# Attribute names that conventionally hold an HTTP client (`self.http`, `deps.session`, ...): an HTTP
# verb called on one is a request through an injected client, even when its type can't be resolved.
CLIENT_ATTRS = {"http", "client", "session", "http_client", "httpclient", "api_client", "apiclient",
                "async_client", "transport", "requests", "httpx"}
BUILTIN_METHOD_NAMES = {
    n for t in (dict, list, str, set, frozenset, tuple, bytes) for n in dir(t) if not n.startswith("_")
}
STDLIB = set(sys.stdlib_module_names) | {"__future__"}
BUILTINS = set(dir(builtins))


# --------------------------------------------------------------------------- dependencies
def _norm(dist: str) -> str:
    return re.sub(r"[-_.]+", "-", dist).lower()


def _split_req(req: str) -> tuple[str, str]:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(.*)", req)
    if not m:
        return "", ""
    return _norm(m.group(1)), m.group(3).split(";")[0].strip()


def _walk_files(match) -> list[Path]:
    """Repo files whose name satisfies `match`, pruning SKIP_DIRS / *.egg-info / the tool's own
    directory / [tool.depscan].skip, sorted."""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        here = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.endswith(".egg-info")
            and (here / d).resolve() != TOOL_DIR and (here / d) not in EXTRA_SKIP
        ]
        out += [here / f for f in filenames if match(f)]
    return sorted(out)


def read_scan_config() -> None:
    """Exclude/skip settings from the target's root pyproject.toml (absent -> none)."""
    global EXTRA_SKIP, EXCLUDE_PATTERNS
    EXTRA_SKIP, EXCLUDE_PATTERNS = [], []
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return
    data = tomllib.loads(pyproject.read_text())
    tool = data.get("tool", {})
    find = tool.get("setuptools", {}).get("packages", {}).get("find", {})
    own = tool.get("depscan", {})
    EXCLUDE_PATTERNS = sorted(set(find.get("exclude", []) + own.get("exclude", [])))
    EXTRA_SKIP = [ROOT / p for p in own.get("skip", [])]


def excluded_by(rel: str) -> str | None:
    """First exclude pattern matching this repo-relative file path, else None."""
    dotted = rel[:-3].replace("/", ".") if rel.endswith(".py") else rel.replace("/", ".")
    first = rel.split("/")[0]
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(dotted, pat) or fnmatch.fnmatch(first, pat):
            return pat
    return None


def dist_import_names(dist: str) -> list[str]:
    """Candidate import names for a distribution: table first, then general heuristics."""
    names = [DIST_TO_IMPORT[dist]] if dist in DIST_TO_IMPORT else []
    base = dist.replace("-", "_")
    names.append(base)
    stripped = re.sub(r"^(python|py)[-_]", "", dist)
    stripped = re.sub(r"[-_](client|sdk|api|python|py)$", "", stripped)
    names.append(stripped.replace("-", "_"))
    if dist.startswith("google-"):
        names.append("google")
    if dist.startswith("azure-"):
        names.append("azure")
    return list(dict.fromkeys(names))


def dependency_files() -> list[Path]:
    return _walk_files(
        lambda f: f == "pyproject.toml" or f in LOCKFILES or re.fullmatch(r"requirements.*\.txt", f)
    )


def read_dependencies() -> dict[str, dict[str, str]]:
    """import name -> {dist, version, version_source}. Lockfile pins beat specs; among specs,
    requirements files are read before pyproject files, each in path order, first one wins."""
    specs: dict[str, tuple[str, str]] = {}  # dist -> (version, source)
    pins: dict[str, tuple[str, str]] = {}
    found = dependency_files()
    rel = lambda p: str(p.relative_to(ROOT))  # noqa: E731

    for req in (p for p in found if p.name.startswith("requirements")):
        for line in req.read_text().splitlines():
            line = line.split("#")[0].strip()
            if line and not line.startswith("-"):
                name, spec = _split_req(line)
                if name:
                    target = pins if re.fullmatch(r"==[^,]+", spec) else specs
                    if name not in target:
                        target[name] = (spec.lstrip("=") if target is pins else spec, rel(req))

    for pyproject in (p for p in found if p.name == "pyproject.toml"):
        proj = tomllib.loads(pyproject.read_text()).get("project", {})
        groups = [proj.get("dependencies", []), *proj.get("optional-dependencies", {}).values()]
        for group in groups:
            for item in group:
                name, spec = _split_req(item)
                if name and name not in specs:
                    specs[name] = (spec, rel(pyproject))

    for lock in (p for p in found if p.name in ("poetry.lock", "uv.lock")):
        for pkg in tomllib.loads(lock.read_text()).get("package", []):
            if pkg.get("version"):
                pins[_norm(pkg["name"])] = (pkg["version"], rel(lock))

    for pipfile in (p for p in found if p.name == "Pipfile.lock"):
        data = json.loads(pipfile.read_text())
        for section in ("default", "develop"):
            for name, meta in data.get(section, {}).items():
                if "version" in meta:
                    pins[_norm(name)] = (meta["version"].lstrip("="), rel(pipfile))

    infos = {}
    for dist in sorted(set(specs) | set(pins)):
        if dist.startswith("types-"):
            continue
        version, source = pins.get(dist) or specs[dist]
        kind = "lockfile" if source.endswith(".lock") else "requirements_spec"
        infos[dist] = {
            "dist": dist,
            "version": version or "unknown",
            "version_source": f"{kind}:{source}" if version else "unknown",
        }
    out: dict[str, dict[str, str]] = {}
    for primary in (True, False):  # primary import names first, heuristic ones only fill gaps
        for dist, info in infos.items():
            names = dist_import_names(dist)
            for imp in names[:1] if primary else names[1:]:
                out.setdefault(imp, info)
    return out


# --------------------------------------------------------------------------- pass 1: index
def module_name(path: Path) -> str:
    root = max(
        (r for r in SOURCE_ROOTS if path.is_relative_to(r)), key=lambda r: len(r.parts), default=ROOT
    )
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def iter_py_files() -> list[Path]:
    return _walk_files(lambda f: f.endswith(".py"))


def detect_source_roots(parsed: list[tuple[Path, ast.Module]]) -> list[Path]:
    """Directories that act as import roots: D is a root if some file imports a top-level name
    that exists as D/<name>/ or D/<name>.py (e.g. `import pi` with src/pi/, `from src.x` from
    inside backend/). The repo root is always one."""
    imported: set[str] = set()
    for _, tree in parsed:
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                imported.add(n.module.split(".")[0])
    imported -= STDLIB
    roots = {ROOT}
    for path, _ in parsed:
        rel = path.relative_to(ROOT).parts
        for i in range(1, len(rel)):
            name = rel[i] if i < len(rel) - 1 else Path(rel[i]).stem
            if name in imported:
                roots.add(ROOT.joinpath(*rel[:i]))
    return sorted(roots)


def load_files() -> tuple[list[FileInfo], list[str]]:
    """Parse every .py file, detect import roots, build FileInfo. Parse failures are returned."""
    global SOURCE_ROOTS
    parsed, sources, errors = [], {}, []
    for path in iter_py_files():
        rel = path.relative_to(ROOT)
        try:
            source = path.read_text(encoding="utf-8")
            parsed.append((path, ast.parse(source, filename=str(rel))))
            sources[path] = source
        except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
            errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    SOURCE_ROOTS = detect_source_roots(parsed)
    return [FileInfo(path, tree, sources[path]) for path, tree in parsed], errors


class FileInfo:
    def __init__(self, path: Path, tree: ast.Module, source: str) -> None:
        self.path = path
        self.rel = str(path.relative_to(ROOT))
        self.mod = module_name(path)
        self.is_pkg = path.name == "__init__.py"
        self.tree = tree
        self.source = source
        self.lines = source.splitlines()
        self.aliases: dict[str, str] = {}
        self.imports: list[str] = []
        self.module_defs: set[str] = set()
        self.consts: dict[str, str] = {}


def _rename(name: str) -> str:
    top, _, rest = name.partition(".")
    return LOCAL_RENAMES.get(top, top) + (f".{rest}" if rest else "")


def collect_imports(fi: FileInfo) -> None:
    # ponytail: one alias map per file (function-level lazy imports included); ignores
    # shadowing between scopes. Fine for a one-off inventory.
    package = fi.mod if fi.is_pkg else fi.mod.rpartition(".")[0]
    for node in ast.walk(fi.tree):
        if isinstance(node, ast.Import):
            fi.imports.append(ast.get_source_segment(fi.source, node) or "")
            for a in node.names:
                if a.asname:
                    fi.aliases[a.asname] = _rename(a.name)
                else:
                    top = a.name.split(".")[0]
                    fi.aliases[top] = _rename(top)
        elif isinstance(node, ast.ImportFrom):
            fi.imports.append(ast.get_source_segment(fi.source, node) or "")
            if node.level:
                base_parts = package.split(".") if package else []
                base_parts = base_parts[: len(base_parts) - (node.level - 1)]
                base = ".".join(base_parts + ([node.module] if node.module else []))
            else:
                base = _rename(node.module or "")
            for a in node.names:
                if a.name != "*":
                    fi.aliases[a.asname or a.name] = f"{base}.{a.name}"
    fi.imports = sorted(set(fi.imports))
    for stmt in fi.tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            fi.module_defs.add(stmt.name)
        elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            t = stmt.targets[0]
            if isinstance(t, ast.Name) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    fi.consts[t.id] = stmt.value.value


def collect_defs(fi: FileInfo, defs: dict[str, dict]) -> None:
    def walk(body: list[ast.stmt], prefix: str) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = f"{prefix}.{stmt.name}"
                src = ast.get_source_segment(fi.source, stmt) or ""
                defs[q] = {
                    "file": fi.rel,
                    "line": stmt.lineno,
                    "kind": "class" if isinstance(stmt, ast.ClassDef) else "function",
                    "in_class": prefix != fi.mod and prefix.split(".")[-1][:1].isupper(),
                    "source": "\n".join(src.splitlines()[:80]),
                }
                walk(stmt.body, q)

    walk(fi.tree.body, fi.mod)


# --------------------------------------------------------------------------- pass 2: calls
class CallScanner(ast.NodeVisitor):
    def __init__(self, fi: FileInfo) -> None:
        self.fi = fi
        self.scopes: list[dict[str, dict]] = [{"vars": {}, "strs": dict(fi.consts)}]
        self.classes: list[str] = []
        self.qual: list[str] = [fi.mod]
        self.attr_env: dict[str, str] = {}
        self.calls: list[dict] = []

    # --- resolution -------------------------------------------------------------------
    def resolve(self, n: ast.AST) -> str | None:
        if isinstance(n, ast.Name):
            for scope in reversed(self.scopes):
                if n.id in scope["vars"]:
                    return scope["vars"][n.id]
            if n.id in self.fi.aliases:
                return self.fi.aliases[n.id]
            if n.id in self.fi.module_defs:
                return f"{self.fi.mod}.{n.id}"
            if n.id in BUILTINS:
                return f"builtins.{n.id}"
            return None
        if isinstance(n, ast.Attribute):
            base = self.resolve(n.value)
            if base is None:
                return None
            full = f"{base}.{n.attr}"
            return self.attr_env.get(full, full)
        if isinstance(n, ast.Call):
            f = self.resolve(n.func)
            return f"{f}()" if f else None
        return None

    def string_value(self, n: ast.AST | None) -> str | None:
        """Best-effort URL text: literals, f-strings, `+` concat, simple names/constants."""
        if n is None:
            return None
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return n.value
        if isinstance(n, ast.JoinedStr):
            out = []
            for v in n.values:
                if isinstance(v, ast.Constant):
                    out.append(str(v.value))
                elif isinstance(v, ast.FormattedValue):
                    inner = self.string_value(v.value)
                    out.append(inner if inner is not None else "{" + ast.unparse(v.value) + "}")
            return "".join(out)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            left, right = self.string_value(n.left), self.string_value(n.right)
            if left is not None or right is not None:
                return (left or "{" + ast.unparse(n.left) + "}") + (
                    right or "{" + ast.unparse(n.right) + "}"
                )
        if isinstance(n, ast.Name):
            for scope in reversed(self.scopes):
                if n.id in scope["strs"]:
                    return scope["strs"][n.id]
        return None

    # --- scopes -----------------------------------------------------------------------
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for d in node.decorator_list:
            self.visit(d)
        self.classes.append(node.name)
        self.qual.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self.qual.pop()
        self.classes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for d in node.decorator_list:
            self.visit(d)
        for default in node.args.defaults + [d for d in node.args.kw_defaults if d]:
            self.visit(default)
        scope: dict[str, dict] = {"vars": {}, "strs": {}}
        args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        for a in args:
            scope["vars"][a.arg] = None  # params shadow imports; value unknown
        if self.classes and args:
            scope["vars"][args[0].arg] = f"{self.fi.mod}.{'.'.join(self.qual[1:])}()"
        self.scopes.append(scope)
        self.qual.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self.qual.pop()
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _bind(self, target: ast.AST, value: ast.AST) -> None:
        resolved = self.resolve(value)
        if isinstance(target, ast.Name):
            self.scopes[-1]["vars"][target.id] = resolved
            s = self.string_value(value)
            if s is None and isinstance(value, ast.Call) and (resolved or "").replace("()", "") in RAW_HTTP_EXACT:
                s = self._url_text(value)  # req = Request(url) -> req carries url
            if s is not None:
                self.scopes[-1]["strs"][target.id] = s
        elif isinstance(target, ast.Attribute) and resolved:
            owner = self.resolve(target.value)
            if owner:
                self.attr_env[f"{owner}.{target.attr}"] = resolved

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for t in node.targets:
            self.visit(t)
            self._bind(t, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
            self._bind(node.target, node.value)

    def visit_With(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._bind(item.optional_vars, item.context_expr)
        for stmt in node.body:
            self.visit(stmt)

    visit_AsyncWith = visit_With

    # --- calls ------------------------------------------------------------------------
    def _url_text(self, node: ast.Call) -> str | None:
        arg = node.args[0] if node.args else None
        for kw in node.keywords:
            if kw.arg in ("url", "fullurl"):
                arg = kw.value
        if arg is None:
            return None
        return self.string_value(arg)

    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        seg = lambda n: ast.get_source_segment(self.fi.source, n) or ast.unparse(n)  # noqa: E731
        args = [seg(a) for a in node.args] + [
            f"{kw.arg}={seg(kw.value)}" if kw.arg else f"**{seg(kw.value)}" for kw in node.keywords
        ]
        self.calls.append(
            {
                "file": self.fi.rel,
                "line": node.lineno,
                "col": node.col_offset,
                "enclosing": ".".join(self.qual),
                "raw_callee": seg(node.func),
                "callee": self.resolve(node.func),
                "args": args,
                "url": self._url_text(node),
            }
        )


# --------------------------------------------------------------------------- classification
def canonical_local(name: str, files_by_mod: dict[str, FileInfo], defs: dict) -> str:
    """Strip call markers and follow package re-exports (`from .x import Y` in __init__)."""
    path = name.replace("()", "")
    for _ in range(8):
        if path in defs:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            mod = ".".join(parts[:i])
            if mod in files_by_mod:
                target = files_by_mod[mod].aliases.get(parts[i])
                if target and target != mod + "." + parts[i]:
                    path = ".".join([target, *parts[i + 1 :]])
                    break
                return path
        else:
            return path
    return path


def detect_renames(files: list, deps: dict, local_tops: set[str]) -> dict[str, str]:
    """A package that imports itself under an old name: unknown top-level `X` is mapped to local
    package `D` when every imported `X.<sub>` exists as module `D.<sub>` (>= 2 distinct subs)."""
    mods = {fi.mod for fi in files}
    prefixes = {m.rsplit(".", i)[0] for m in mods for i in range(m.count(".") + 1)}
    subs: dict[str, set[str]] = {}
    for fi in files:
        for n in ast.walk(fi.tree):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else (
                [n.module] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else [])
            for name in names:
                top, _, rest = name.partition(".")
                if rest and top not in STDLIB and top not in local_tops and top not in deps:
                    subs.setdefault(top, set()).add(rest)
    renames = {}
    for top, rests in sorted(subs.items()):
        if len(rests) < 2:
            continue
        hits = [d for d in sorted(local_tops) if all(f"{d}.{r}" in prefixes for r in rests)]
        if len(hits) == 1:
            renames[top] = hits[0]
    return renames


def client_attr_call(raw_callee: str) -> bool:
    """`<anything>.<client-like attribute>.<HTTP verb>` — e.g. `self.deps.http.post`."""
    parts = raw_callee.split(".")
    return len(parts) >= 3 and parts[-1] in HTTP_VERBS and parts[-2].lstrip("_").lower() in CLIENT_ATTRS


def preliminary(call: dict, deps: dict, local_tops: set[str]) -> tuple[str, str]:
    callee = call["callee"]
    top = (callee or "").split(".")[0]
    if (callee is None or top in local_tops) and client_attr_call(call["raw_callee"]):
        return "client_call", f"HTTP-style `{call['raw_callee'].rsplit('.', 1)[-1]}` on a client attribute (injected client)"
    if callee is None:
        return "unresolved", ""
    plain = callee.replace("()", "")
    if callee in STDLIB_CLIENTS:
        return "stdlib_client", f"stdlib network client {plain}"
    # Raw HTTP = a package function (`httpx.get`) or a verb one constructor deep (`httpx.Client().get`);
    # deeper chains like `httpx.get().json().get` are response handling, not requests (0.5.0).
    if callee in RAW_HTTP_EXACT or (
        top in RAW_HTTP_PKGS
        and ("()" not in callee or (callee.count("()") == 1 and callee.rsplit(".", 1)[-1] in HTTP_VERBS))
    ):
        return "raw_http", f"raw HTTP via {plain}"
    if top in local_tops:
        return "local", ""
    if top == "builtins" or top in STDLIB:
        return "stdlib", ""
    if top in LOCAL_ONLY_PACKAGES:
        return "local_lib", ""
    if top in deps:
        return "known_sdk", ""
    return "undeclared", f"third-party package `{top}` not declared in any dependency file"


def run(root: Path, out: Path) -> dict:
    """Scan one repository; write known_sdk.json, unclear.json, scan_meta.json and
    parse_errors.txt into `out`; return the scan metadata. Not re-entrant (module state)."""
    global ROOT, OUT
    ROOT, OUT = Path(root).resolve(), Path(out).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    read_scan_config()
    deps = read_dependencies()
    files, parse_errors = load_files()
    (OUT / "parse_errors.txt").write_text("".join(f"{e}\n" for e in parse_errors))

    files_by_mod = {fi.mod: fi for fi in files}
    local_tops = {fi.mod.split(".")[0] for fi in files}
    LOCAL_RENAMES.clear()
    LOCAL_RENAMES.update(detect_renames(files, deps, local_tops))
    defs: dict[str, dict] = {}
    for fi in files:
        collect_imports(fi)
        collect_defs(fi, defs)

    calls: list[dict] = []
    for fi in files:
        scanner = CallScanner(fi)
        scanner.visit(fi.tree)
        calls.extend(scanner.calls)
    calls.sort(key=lambda c: (c["file"], c["line"], c["col"]))

    for c in calls:
        c["_kind"], c["_reason"] = preliminary(c, deps, local_tops)
        c["_local"] = (
            canonical_local(c["callee"], files_by_mod, defs) if c["_kind"] == "local" else None
        )

    # wrappers: local functions whose own body directly makes an SDK / raw-HTTP / undeclared call.
    # ponytail: one level deep on purpose — transitive closure flags the whole pipeline + CLI.
    wrappers = {
        c["enclosing"]
        for c in calls
        if c["_kind"] in ("known_sdk", "raw_http", "stdlib_client", "client_call")
        or (c["_kind"] == "undeclared" and c["callee"].split(".")[0] not in INBOUND_SERVER_PACKAGES)
    }
    # Only functions can be wrappers: calls in a class body (ORM column definitions, ...) used to make
    # every instantiation of that class look like an external call (0.5.0).
    wrappers = {w for w in wrappers if defs.get(w, {}).get("kind") != "class"}
    # Method names that built-in types also have (get, pop, update, ...) are never bare-matched: a
    # `.get(` is almost always a dict lookup, and matching it flagged every dict access in a repo (0.2.0).
    wrapper_methods = {w.rsplit(".", 1)[1] for w in wrappers if defs.get(w, {}).get("in_class")}
    wrapper_methods -= BUILTIN_METHOD_NAMES

    known, unclear, counts = [], [], Counter()
    for c in calls:
        kind, reason = c["_kind"], c["_reason"]
        local = c["_local"]
        last_attr = c["raw_callee"].rsplit(".", 1)[-1]
        if kind == "local" and local in wrappers:
            kind, reason = "wrapper", f"local wrapper `{local}` makes external calls"
        elif kind in ("local", "unresolved") and "." in c["raw_callee"] and last_attr in wrapper_methods:
            impls = sorted(w for w in wrappers if w.endswith("." + last_attr))
            kind = "dynamic_client"
            reason = f"method `{last_attr}` on a dynamically built client; implementations: {impls}"

        base = {k: c[k] for k in ("file", "line", "callee", "raw_callee", "args")}
        base["url"] = c["url"] if kind in ("raw_http", "wrapper", "stdlib_client", "client_call") else None
        base["excluded_by"] = excluded_by(c["file"])
        if kind in ("known_sdk", "raw_http", "undeclared", "wrapper", "dynamic_client", "stdlib_client", "client_call"):
            fi = files_by_mod[module_name(ROOT / c["file"])]
            lo = max(0, c["line"] - 11)
            factory = None
            if kind == "dynamic_client" and c["callee"]:
                factory = canonical_local(c["callee"].rsplit("()", 1)[0], files_by_mod, defs)
            called = local if kind == "wrapper" else factory
            ctx = {
                "context": "\n".join(
                    f"{i + 1:>4}{'>' if i + 1 == c['line'] else ' '} {fi.lines[i]}"
                    for i in range(lo, min(len(fi.lines), c["line"] + 10))
                ),
                "file_imports": fi.imports,
                "called_function": called if called in defs else None,
                "called_function_source": defs[called]["source"] if called in defs else None,
                "enclosing": c["enclosing"],
            }
        if kind == "known_sdk":
            top = c["callee"].split(".")[0]
            known.append({**base, "class": "known_sdk", "package": top, **{
                k: deps[top][k] for k in ("dist", "version", "version_source")
            }, "reason": f"call into declared package `{top}`", **ctx})
            counts["known_sdk"] += 1
        elif kind in ("raw_http", "undeclared", "wrapper", "dynamic_client", "stdlib_client", "client_call"):
            unclear.append({**base, "class": "unclear", "unclear_kind": kind, "reason": reason, **ctx})
            counts["unclear"] += 1
        else:
            counts["ignored"] += 1

    (OUT / "known_sdk.json").write_text(json.dumps(known, indent=2) + "\n")
    (OUT / "unclear.json").write_text(json.dumps(unclear, indent=2) + "\n")
    meta = {
        "root": str(ROOT),
        "dependency_files": [str(p.relative_to(ROOT)) for p in dependency_files()],
        "dependencies": deps,
        "import_roots": [str(r.relative_to(ROOT)) or "." for r in SOURCE_ROOTS],
        "renames": dict(LOCAL_RENAMES),
        "exclude_patterns": EXCLUDE_PATTERNS,
        "skip": [str(p.relative_to(ROOT)) for p in EXTRA_SKIP],
        "files_scanned": len(files),
        "parse_failures": parse_errors,
        "call_sites": len(calls),
        "counts": {k: counts[k] for k in ("known_sdk", "unclear", "ignored")},
        "unclear_by_kind": dict(sorted(Counter(u["unclear_kind"] for u in unclear).items())),
        "known_sdk_by_package": dict(sorted(Counter(k["package"] for k in known).items())),
    }
    (OUT / "scan_meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    return meta
