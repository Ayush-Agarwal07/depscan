"""Step 3 — label the calls static analysis couldn't resolve, with an LLM.

Providers: `anthropic` (API key + the optional `anthropic` package), `claude-cli` (`claude -p`,
headless Claude Code on the user's own Claude login — no API key needed), `ollama` (local).
Defaults: claude-opus-5-5 for Claude providers, gemma4:12b for Ollama (DEPSCAN_*_MODEL env vars
or --model override).

- Cache: <cache>/<sha256>.json keyed by provider + model + system prompt + entry context, so a
  rerun makes zero calls and editing the prompt or model invalidates stale answers. Answers that
  stay invalid after every retry are cached too (as invalid, with their retry log), so a rerun is
  deterministic; set DEPSCAN_RETRY_INVALID=1 to retry them. Each record keeps its token usage so
  cold-run cost stays reportable.
- Invalid JSON / schema / refusal / transport error -> retried up to 3 more times. A retry after
  an invalid answer sends that answer back with the validation errors and asks for a corrected
  object (and uses a different seed), so a deterministic model can't repeat the same mistake.
- version_hint is kept only if it appears literally in the context, else nulled and recorded.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from depscan import aliases

ANTHROPIC_MODEL = "claude-opus-5-5"
ANTHROPIC_PRICE = {"input": 4.00 / 1e6, "output": 20.00 / 1e6}  # USD per token, opus 5.5
OLLAMA_MODEL = os.getenv("DEPSCAN_OLLAMA_MODEL", "gemma4:12b")
CLAUDE_MODEL = os.getenv("DEPSCAN_CLAUDE_MODEL", "claude-opus-5-5")
OLLAMA_URL = os.getenv("DEPSCAN_OLLAMA_URL", "http://localhost:11434")
MAX_RETRIES = 3
WORKERS = int(os.getenv("DEPSCAN_WORKERS", "4"))
FIELDS = [
    "is_external_api", "provider", "service", "canonical_name", "default_target",
    "hosting", "version_hint", "confidence", "reasoning",
]
NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
SCHEMA = {
    "type": "object",
    "properties": {
        "is_external_api": {"type": "boolean"},
        "provider": NULLABLE_STR,
        "service": NULLABLE_STR,
        "canonical_name": NULLABLE_STR,
        "default_target": NULLABLE_STR,
        "hosting": {"anyOf": [{"type": "string", "enum": ["cloud", "self-hosted"]}, {"type": "null"}]},
        "version_hint": NULLABLE_STR,
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": FIELDS,
    "additionalProperties": False,
}
CANONICAL_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*/[a-z0-9][a-z0-9.-]*$")

SYSTEM_PROMPT = """\
You classify evidence from a Python codebase for a dependency inventory: does it reach a \
service outside the current process, and if so which one?

Each input is one of two kinds:
- "input kind: call" — one call site that static analysis could not resolve. You get the \
surrounding code, the file's imports, the source of the called function when it is local, and \
(for configurable endpoints) the lines where an attribute's value is set.
- "input kind: package" — one third-party package the repository declares, with sample call \
sites. Decide whether the package, as used here, reaches an external service; purely local \
libraries (parsers, data frames, crypto, CLIs, terminal UIs, retry helpers) are not external.
Decide from the evidence only.

Return one JSON object with these fields:
- is_external_api: true for any service outside this process, including local ones \
(a localhost daemon, a database file engine, a model download hub). false for purely \
in-process code, local file I/O, and in-process libraries.
- provider, service: who runs it and which service. null when is_external_api is false.
- canonical_name: lowercase "provider/service", using only a-z 0-9 . - in each part, e.g. \
"aws/s3", "stooq/daily-prices", "ollama/chat". When the endpoint is configurable by env var or \
constructor argument, name the protocol, e.g. "openai-compatible/chat-completions", and put the \
default target in default_target (e.g. "openai"). null when is_external_api is false.
- Naming consistency: if the service is one of these known services, use exactly this name: {known_names}. Otherwise use the operating organization as provider and the API product as service; never use a placeholder provider such as "generic" or "unknown". If the target host is not fixed by the code (a URL supplied at runtime), use "web/arbitrary-url".
- default_target: the provider the configurable endpoint points at by default, else null.
- hosting: "cloud" or "self-hosted" (Ollama, Redis, SQLite, Postgres are self-hosted). \
null when is_external_api is false.
- version_hint: ONLY a version string that appears literally in the provided code, such as a \
URL path segment ("v8", "v1") or a header value. Never infer a version from your own \
knowledge, package names, or dependency specs. Otherwise null.
- confidence: 0 to 1.
- reasoning: one sentence.

Dispatch sites: a call that only selects or forwards to a backend chosen elsewhere (a client \
factory, a provider router, a method on an injected or dynamically built client whose \
concrete implementation lives at another call site) is NOT itself an external call — answer \
is_external_api false with reasoning starting "dispatch:". The concrete call site that \
actually sends the request is labelled where it occurs.

Examples (illustrative code, not from this repository):

1. SDK call
code: client = anthropic.Anthropic(api_key=key)
      msg = client.messages.create(model=m, max_tokens=512, messages=msgs)
answer: {"is_external_api": true, "provider": "anthropic", "service": "messages", \
"canonical_name": "anthropic/messages", "default_target": null, "hosting": "cloud", \
"version_hint": null, "confidence": 0.98, "reasoning": "Official Anthropic SDK client \
calling the Messages API; no version string appears in the code."}

2. Raw HTTP with a literal URL
code: req = urllib.request.Request(f"https://api.stripe.com/v1/charges/{charge_id}", \
headers=auth)
      with urllib.request.urlopen(req) as r: ...
answer: {"is_external_api": true, "provider": "stripe", "service": "charges", \
"canonical_name": "stripe/charges", "default_target": null, "hosting": "cloud", \
"version_hint": "v1", "confidence": 0.97, "reasoning": "Literal Stripe API URL with a /v1/ \
path segment."}

3. Configurable base_url
code: self.base_url = base_url.rstrip("/")
      requests.post(f"{self.base_url}/embeddings", json=body)
where self.base_url's value comes from:
      factory.py:12: base_url=os.getenv("EMBED_BASE_URL", "https://api.openai.com/v1")
answer: {"is_external_api": true, "provider": "openai-compatible", "service": "embeddings", \
"canonical_name": "openai-compatible/embeddings", "default_target": "openai", \
"hosting": "cloud", "version_hint": "v1", "confidence": 0.9, "reasoning": "Env-configurable \
OpenAI-compatible embeddings endpoint whose default is api.openai.com/v1."}

4. Self-hosted service
code: conn = psycopg.connect(os.getenv("DATABASE_URL", "postgresql://localhost:5432/app"))
answer: {"is_external_api": true, "provider": "postgresql", "service": "database", \
"canonical_name": "postgresql/database", "default_target": null, "hosting": "self-hosted", \
"version_hint": null, "confidence": 0.95, "reasoning": "Connects to a PostgreSQL server, \
defaulting to localhost."}

5. Non-API wrapper
code: def load_cache(path): return json.loads(Path(path).read_text())
      data = load_cache(CACHE_FILE)
answer: {"is_external_api": false, "provider": null, "service": null, \
"canonical_name": null, "default_target": null, "hosting": null, "version_hint": null, \
"confidence": 0.96, "reasoning": "Reads a local JSON file; nothing leaves the process."}

6. Dispatch site
code: def get_store(kind=os.getenv("STORE", "file")):
          return S3Store() if kind == "s3" else FileStore()
      store = get_store()
      store.save(doc)
answer: {"is_external_api": false, "provider": null, "service": null, \
"canonical_name": null, "default_target": null, "hosting": null, "version_hint": null, \
"confidence": 0.9, "reasoning": "dispatch: store is chosen at runtime; S3 is reached inside \
S3Store.save, which is labelled at that call site."}

7. Local-only package
input kind: package — tabulate, sample: print(tabulate(rows, headers="keys"))
answer: {"is_external_api": false, "provider": null, "service": null, \
"canonical_name": null, "default_target": null, "hosting": null, "version_hint": null, \
"confidence": 0.97, "reasoning": "tabulate formats tables in memory; no network or service."}
""".replace("{known_names}", ", ".join(sorted(
    {name for name, _ in aliases.SDK_ALIASES.values()}
    | {"sqlite/database", "google/gemini", "aws/<service>", "gcp/<product>", "azure/<product>"}
)))
PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()


# --------------------------------------------------------------------------- providers
class AnthropicProvider:
    name = "anthropic"
    model = ANTHROPIC_MODEL

    def __init__(self) -> None:
        import anthropic

        self.client = anthropic.Anthropic()

    def complete(self, context: str, feedback: tuple[str, str] | None = None,
                 attempt: int = 1) -> tuple[str, str | None, dict]:
        messages = [{"role": "user", "content": context}]
        if feedback:
            messages += [{"role": "assistant", "content": feedback[0]}, {"role": "user", "content": feedback[1]}]
        msg = self.client.beta.messages.create(
            model=self.model,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        return text, msg.stop_reason, usage

    def cost(self, usage: dict) -> float:
        return usage.get("input_tokens", 0) * ANTHROPIC_PRICE["input"] + \
            usage.get("output_tokens", 0) * ANTHROPIC_PRICE["output"]

    @staticmethod
    def fatal(exc: Exception) -> bool:
        import anthropic

        return isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
                                anthropic.BadRequestError, anthropic.NotFoundError))


class OllamaProvider:
    name = "ollama"

    def __init__(self) -> None:
        self.model = OLLAMA_MODEL

    def complete(self, context: str, feedback: tuple[str, str] | None = None,
                 attempt: int = 1) -> tuple[str, str | None, dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": context}]
        if feedback:
            messages += [{"role": "assistant", "content": feedback[0]}, {"role": "user", "content": feedback[1]}]
        body = {
            "model": self.model, "stream": False, "think": False, "format": SCHEMA,
            "options": {"temperature": 0, "seed": attempt - 1, "num_ctx": 16384, "num_predict": 1024},
            "messages": messages,
        }
        req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:  # noqa: S310 — local model server
            payload = json.loads(r.read())
        usage = {"input_tokens": payload.get("prompt_eval_count", 0), "output_tokens": payload.get("eval_count", 0)}
        return payload["message"]["content"], payload.get("done_reason"), usage

    def cost(self, usage: dict) -> float:
        return 0.0  # local model

    @staticmethod
    def fatal(exc: Exception) -> bool:
        return False


class TransportError(RuntimeError):
    """The model call itself failed (rate limit, timeout, CLI error) — never cached."""


class ClaudeCLIProvider:
    """Claude via `claude -p` (headless Claude Code) on the user's subscription login.

    Isolated per call: no tools, no MCP servers, no settings, no session persistence, run from
    an empty temp dir, with ANTHROPIC_API_KEY removed so the subscription (not an API key) is
    used. Structured output via --json-schema. `cost_usd` is the CLI's notional list-price cost;
    on a subscription it draws on plan usage limits rather than being billed.
    """

    name = "claude-cli"

    def __init__(self) -> None:
        self.model = CLAUDE_MODEL
        self.exe = shutil.which("claude") or sys.exit("claude CLI not found on PATH")
        self.cwd = tempfile.mkdtemp(prefix="classify-claude-")
        self.env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    def complete(self, context: str, feedback: tuple[str, str] | None = None,
                 attempt: int = 1) -> tuple[str, str | None, dict]:
        prompt = context
        if feedback:
            prompt += (f"\n\n--- your previous answer ---\n{feedback[0]}\n--- problem ---\n{feedback[1]}")
        cmd = [self.exe, "-p", "--model", self.model, "--effort", "low", "--tools", "",
               "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
               "--output-format", "json", "--system-prompt", SYSTEM_PROMPT, "--json-schema", json.dumps(SCHEMA)]
        try:
            run = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=600,
                                 cwd=self.cwd, env=self.env)
        except subprocess.TimeoutExpired as exc:
            raise TransportError(f"claude -p timed out: {exc}") from exc
        try:
            out = json.loads(run.stdout)
        except json.JSONDecodeError as exc:
            raise TransportError(f"claude -p rc={run.returncode} non-JSON output: {run.stdout[:200]!r} {run.stderr[:200]!r}") from exc
        if out.get("is_error") or out.get("subtype") != "success":
            if out.get("api_error_status") == 429 or "limit" in str(out.get("result", "")).lower():
                time.sleep(60)  # back off on rate/usage limits before the next attempt
            raise TransportError(f"claude -p error: {out.get('subtype')} {out.get('api_error_status')} {str(out.get('result'))[:200]}")
        u = out.get("usage") or {}
        usage = {
            "input_tokens": (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
            + (u.get("cache_read_input_tokens") or 0),
            "output_tokens": u.get("output_tokens") or 0,
            "cost_usd": out.get("total_cost_usd") or 0.0,
        }
        text = json.dumps(out["structured_output"]) if out.get("structured_output") is not None else (out.get("result") or "")
        stop = "refusal" if out.get("stop_reason") == "refusal" else out.get("stop_reason")
        return text, stop, usage

    def cost(self, usage: dict) -> float:
        return usage.get("cost_usd", 0.0)

    @staticmethod
    def fatal(exc: Exception) -> bool:
        return False


PROVIDERS = ("anthropic", "claude-cli", "ollama")


def provider_available(name: str) -> tuple[bool, str]:
    """(usable?, reason) — cheap checks, no model call."""
    if name == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            return False, "ANTHROPIC_API_KEY is not set"
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False, "the `anthropic` package is not installed (pip install 'depscan[anthropic]')"
        return True, "API key"
    if name == "claude-cli":
        return (True, "claude CLI on PATH") if shutil.which("claude") else (False, "`claude` (Claude Code) is not on PATH")
    if name == "ollama":
        try:
            urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2).read()  # noqa: S310 — local server
            return True, f"Ollama at {OLLAMA_URL}"
        except OSError:
            return False, f"no Ollama server at {OLLAMA_URL}"
    return False, f"unknown provider {name!r}"


def auto_provider() -> str | None:
    """First available of: anthropic (API key) -> claude-cli -> ollama; None if none."""
    for name in PROVIDERS:
        if provider_available(name)[0]:
            return name
    return None


def make_provider(name: str, model: str | None = None) -> Any:
    provider = {"anthropic": AnthropicProvider, "claude-cli": ClaudeCLIProvider, "ollama": OllamaProvider}[name]()
    if model:
        provider.model = model
    return provider


# --------------------------------------------------------------------------- core
def cache_key(provider: str, model: str, context: str) -> str:
    blob = json.dumps({"provider": provider, "model": model, "system": SYSTEM_PROMPT, "context": context},
                      sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def validate(data: Any, context: str) -> tuple[dict | None, list[str], str | None]:
    """-> (clean result | None, errors, rejected version_hint)."""
    if not isinstance(data, dict):
        return None, ["response is not a JSON object"], None
    errors = []
    if sorted(data) != sorted(FIELDS):
        return None, [f"fields {sorted(data)} != {sorted(FIELDS)}"], None
    if not isinstance(data["is_external_api"], bool):
        errors.append("is_external_api not bool")
    conf = data["confidence"]
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0 <= conf <= 1:
        errors.append(f"confidence {conf!r} not in [0, 1]")
    if not isinstance(data["reasoning"], str) or not data["reasoning"].strip():
        errors.append("reasoning empty")
    for f in ("provider", "service", "canonical_name", "default_target", "hosting", "version_hint"):
        if data[f] is not None and not isinstance(data[f], str):
            errors.append(f"{f} not string/null")
    if data["is_external_api"] is True:
        if not data["provider"] or not data["service"]:
            errors.append("external but provider/service missing")
        if not isinstance(data["canonical_name"], str) or not CANONICAL_RE.match(data["canonical_name"]):
            errors.append(f"canonical_name {data['canonical_name']!r} not lowercase provider/service")
        if data["hosting"] not in ("cloud", "self-hosted"):
            errors.append(f"hosting {data['hosting']!r} not cloud/self-hosted")
    if errors:
        return None, errors, None
    clean = dict(data)
    rejected = None
    if clean["version_hint"] is not None and clean["version_hint"] not in context:
        rejected, clean["version_hint"] = clean["version_hint"], None  # never invented
    return clean, [], rejected


class Classifier:
    def __init__(self, provider: Any, cache_dir: Path) -> None:
        self.provider = provider
        self.cache_dir = cache_dir
        self.api_calls = 0
        self.cache_hits = 0
        self.fresh_usage = {"input_tokens": 0, "output_tokens": 0}
        self.fresh_seconds = 0.0
        self._lock = threading.Lock()

    def classify(self, entry: dict) -> dict:
        context = entry["llm_context"]
        key = cache_key(self.provider.name, self.provider.model, context)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            cached = json.loads(path.read_text())
            if cached["valid"] or not os.getenv("DEPSCAN_RETRY_INVALID"):
                with self._lock:
                    self.cache_hits += 1
                return {**cached, "from_cache": True}

        failures, usage_total, seconds = [], {"input_tokens": 0, "output_tokens": 0}, 0.0
        transport_failed = False
        feedback: tuple[str, str] | None = None  # (previous answer, what was wrong with it)
        for attempt in range(1, MAX_RETRIES + 2):
            t0 = time.monotonic()
            try:
                with self._lock:
                    self.api_calls += 1
                text, stop, usage = self.provider.complete(context, feedback=feedback, attempt=attempt)
            except Exception as exc:  # noqa: BLE001
                if self.provider.fatal(exc):
                    raise
                transport_failed = True
                failures.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
                continue
            finally:
                seconds += time.monotonic() - t0
            for k, v in usage.items():
                usage_total[k] = usage_total.get(k, 0) + (v or 0)
            if stop == "refusal":
                failures.append(f"attempt {attempt}: refusal")
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                failures.append(f"attempt {attempt}: invalid JSON ({exc}): {text[:120]!r}")
                feedback = (text[:2000], f"That was not valid JSON ({exc}). Reply with one corrected JSON object only.")
                continue
            clean, errors, rejected = validate(data, context)
            if clean is None:
                failures.append(f"attempt {attempt}: schema: {'; '.join(errors)}")
                feedback = (text[:2000], "That answer is invalid: " + "; ".join(errors) + ". Fix exactly these "
                            "problems and reply with one corrected JSON object only (if is_external_api is true, "
                            "hosting must be \"cloud\" or \"self-hosted\" and provider/service/canonical_name must be set).")
                continue
            record = {
                "cache_key": key, "result": clean, "version_hint_rejected": rejected,
                "attempts": attempt, "retry_log": failures, "provider": self.provider.name,
                "model_used": self.provider.model, "usage": usage_total,
                "llm_seconds": round(seconds, 3), "valid": True,
            }
            self._write(path, record)
            self._add_fresh(usage_total, seconds)
            return {**record, "from_cache": False}
        self._add_fresh(usage_total, seconds)
        record = {"cache_key": key, "result": None, "valid": False, "attempts": MAX_RETRIES + 1,
                  "retry_log": failures, "version_hint_rejected": None, "provider": self.provider.name,
                  "model_used": self.provider.model, "usage": usage_total,
                  "llm_seconds": round(seconds, 3)}
        if not transport_failed:  # cache model failures; a transport error deserves a later retry
            self._write(path, record)
        return {**record, "from_cache": False}

    def _write(self, path: Path, record: dict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        tmp.replace(path)

    def _add_fresh(self, usage: dict, seconds: float) -> None:
        with self._lock:
            for k, v in usage.items():
                self.fresh_usage[k] = self.fresh_usage.get(k, 0) + (v or 0)
            self.fresh_seconds += seconds


KEEP = ["id", "kind", "file", "line", "callee", "raw_callee", "package", "scan_class", "scan_kind",
        "url", "excluded_by", "dist", "version", "version_source", "call_sites", "endpoint_override"]


def run(provider: Any, inputs: list[dict], cache_dir: Path) -> tuple[list[dict], dict]:
    clf = Classifier(provider, cache_dir)
    t0 = time.monotonic()
    with ThreadPoolExecutor(WORKERS) as pool:
        records = list(pool.map(clf.classify, inputs))
    wall = time.monotonic() - t0
    results = []
    for entry, rec in zip(inputs, records, strict=True):
        results.append({
            **{k: entry.get(k) for k in KEEP},
            "valid": rec["valid"],
            **{f: (rec["result"] or {}).get(f) for f in FIELDS},
            "version_hint_rejected": rec["version_hint_rejected"],
            "attempts": rec["attempts"], "retry_log": rec["retry_log"],
            "model_used": rec["model_used"], "cache_key": rec["cache_key"],
        })
    keys = sorted({k for r in records for k in (r.get("usage") or {})} | set(clf.fresh_usage))
    all_usage = {k: sum((r.get("usage") or {}).get(k, 0) for r in records) for k in keys}
    stats = {
        "provider": provider.name,
        "model": provider.model,
        "prompt_sha256": PROMPT_SHA256,
        "entries": len(inputs),
        "valid": sum(r["valid"] for r in records),
        "invalid": sum(not r["valid"] for r in records),
        "api_calls": clf.api_calls,
        "cache_hits": clf.cache_hits,
        "tokens_fresh": clf.fresh_usage,
        "tokens_all": all_usage,  # what a cold run of this mode costs (cached records keep usage)
        "cost_usd_fresh": round(provider.cost(clf.fresh_usage), 4),
        "cost_usd_all": round(provider.cost(all_usage), 4),
        "llm_seconds_fresh": round(clf.fresh_seconds, 1),
        "llm_seconds_all": round(sum(r.get("llm_seconds", 0) for r in records), 1),
        "classify_wall_seconds": round(wall, 1),
        "workers": WORKERS,
    }
    return results, stats


def selfcheck() -> None:
    """Stub provider: invalid JSON then valid; invented version dropped; rerun is all cache."""
    import tempfile

    replies = [
        "not json",
        json.dumps({"is_external_api": True, "provider": "stooq", "service": "daily-prices",
                    "canonical_name": "stooq/daily-prices", "default_target": None,
                    "hosting": "cloud", "version_hint": "v9", "confidence": 0.9,
                    "reasoning": "Literal stooq URL."}),
    ]

    class Stub:
        name, model = "stub", "stub-1"

        def complete(self, context: str, feedback=None, attempt: int = 1) -> tuple[str, str, dict]:
            if attempt == 2:
                assert feedback and "not valid JSON" in feedback[1], feedback  # retry carries the error
            return replies.pop(0), "end_turn", {"input_tokens": 100, "output_tokens": 10}

        def cost(self, usage: dict) -> float:
            return 0.0

        @staticmethod
        def fatal(exc: Exception) -> bool:
            return False

    entry = {"id": "x.py:1:f", "kind": "call", "file": "x.py", "line": 1,
             "llm_context": "url = 'https://stooq.com/q/d/l/?s=aapl.us&i=d'"}
    with tempfile.TemporaryDirectory() as tmp:
        results, stats = run(Stub(), [entry], Path(tmp))
        r = results[0]
        assert r["valid"] and r["attempts"] == 2 and stats["api_calls"] == 2, (r, stats)
        assert r["version_hint"] is None and r["version_hint_rejected"] == "v9", r
        assert stats["tokens_fresh"] == {"input_tokens": 200, "output_tokens": 20}, stats
        results2, stats2 = run(Stub(), [entry], Path(tmp))
        assert stats2["api_calls"] == 0 and stats2["cache_hits"] == 1 and results2 == results, stats2
        assert stats2["tokens_all"] == stats["tokens_fresh"] and stats2["tokens_fresh"]["input_tokens"] == 0
    with tempfile.TemporaryDirectory() as tmp:  # exhausted retries are cached -> rerun makes 0 calls
        replies[:] = ["not json"] * (MAX_RETRIES + 1)
        res, st = run(Stub(), [entry], Path(tmp))
        assert not res[0]["valid"] and st["api_calls"] == MAX_RETRIES + 1, st
        res2, st2 = run(Stub(), [entry], Path(tmp))
        assert st2["api_calls"] == 0 and res2 == res, st2
    bad = {f: None for f in FIELDS} | {"is_external_api": True, "confidence": 0.5, "reasoning": "x"}
    assert validate(bad, "")[0] is None
    assert validate({**bad, "provider": "P", "service": "s", "canonical_name": "Bad Name",
                     "hosting": "cloud"}, "")[0] is None
    print("selfcheck ok: retry on invalid JSON, version guard, cache -> 0 calls, usage kept for cold cost")


def classify_dir(run_dir: Path, cache_dir: Path, provider: Any) -> dict:
    """Classify <run_dir>/llm_inputs.json; write llm_results.json + classify_stats.json; return stats."""
    run_dir = Path(run_dir)
    inputs = json.loads((run_dir / "llm_inputs.json").read_text())
    results, stats = run(provider, inputs, Path(cache_dir))
    (run_dir / "llm_results.json").write_text(json.dumps(results, indent=2) + "\n")
    (run_dir / "classify_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    return stats
