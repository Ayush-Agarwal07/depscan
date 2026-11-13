# components.json

```jsonc
{
  "mode": "hybrid",                       // static | llm_only | hybrid
  "repo": "/abs/path/to/repo",
  "components": [
    {
      "canonical_name": "openai/chat-completions",   // lowercase provider/service
      "hosting": "cloud",                            // cloud | self-hosted | unknown (static mode)
      "default_target": null,          // for configurable endpoints: the provider it points at by default
      "package_name": "openai",        // client package, for SDK-backed components
      "package_version": "1.50.0",     // exact pin from a lockfile or ==, else null
      "declared_range": null,          // the declared spec when it isn't an exact pin
      "installed_version": null,       // only with --installed-versions
      "api_version": "v1",             // only if literally in the code (URL path / header)
      "api_versions_seen": ["v1"],
      "version_source": "package: lockfile:uv.lock; api: literal in code",
      "excluded": false,               // true if every use is under an excluded path
      "found_by": {"static-alias": 3, "llm-call": 1},  // how many call sites each route found
      "min_confidence": 0.9,           // lowest LLM confidence among its call sites (null if none)
      "merged_from": [],               // other names merged into this one
      "evidence": [                    // every call site
        {"location": "app/llm.py:42", "callee": "openai.OpenAI().chat.completions.create",
         "found_by": "static-alias", "scan_kind": "known_sdk", "excluded_by": null, "confidence": null}
      ]
    }
  ],
  "inbound": {"role": "inbound", "packages": {"fastapi": 12}, "call_sites": 12, "evidence": ["app/main.py:5"]},
  "hosting_conflicts": [],            // components whose call sites disagreed on hosting
  "renames_detected": {},             // packages that import themselves under an old name
  "exclude_patterns": ["tests*"]
}
```

`found_by` values: `static-alias` (known SDK table), `static-fallback` (static mode's `<package>/sdk`
guess), `llm-call` (an LLM answer about one call site), `llm-package` (an LLM answer about a whole
package, applied to all its call sites).

`scan_kind` values: `known_sdk`, `package`, `raw_http`, `client_call`, `stdlib_client`, `wrapper`,
`dynamic_client`, `undeclared` — see [HOW_IT_WORKS.md](HOW_IT_WORKS.md).
