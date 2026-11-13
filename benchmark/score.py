"""Score benchmark runs against the frozen labels. Deterministic (no timestamps).

    python benchmark/score.py            # writes benchmark/results/

Matching (one-to-one, greedy, in this order; each pair records how it matched):
  1. name      normalized names equal (after SCORER_ALIASES)
  2. evidence  a tool evidence line within ±LINE_WINDOW lines of a label evidence line, same file
  3. provider  normalized providers equal
A manual adjudication list (results/match_adjudication.json) forbids pairs that the evidence/
provider rules made but that are different services, plus placeholder / generic-HTTP-client
tool names that never match a named service. Precision = matched tool components / tool
components; recall = matched labels / labels. Strict = name matches only. Name accuracy =
name-matched pairs / matched pairs. Version accuracy counts labeled versions only.
Results are reported per repo and as micro-averages over the dev set, the held-out set and all.
"""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOS_META = json.loads((HERE / "repos.json").read_text())
REPOS = [r["name"] for r in REPOS_META]
SET_OF = {r["name"]: r["set"] for r in REPOS_META}
MODES = ["static", "llm_only", "hybrid"]
LINE_WINDOW = 3

# Scorer-side alias table. Frozen before any benchmark-repo tool output existed (D-36):
# generic spelling synonyms only, applied to BOTH label and tool names.
SCORER_ALIASES = {
    "providers": {
        "hugging-face": "huggingface", "hf": "huggingface", "postgres": "postgresql",
        "amazon": "aws", "amazon-web-services": "aws", "google-cloud": "gcp",
    },
    "services": {},  # none: service-name differences are what "name accuracy" measures
}


def norm(name: str) -> str:
    name = re.sub(r"[\s_]+", "-", name.strip().lower())
    provider, _, service = name.partition("/")
    provider = SCORER_ALIASES["providers"].get(provider, provider)
    service = SCORER_ALIASES["services"].get(service, service)
    return f"{provider}/{service}"


def provider(name: str) -> str:
    return norm(name).split("/")[0]


def parse_loc(loc: str) -> tuple[str, int]:
    f, _, line = loc.rpartition(":")
    return f, int(line)


def overlap(tool_locs: list[str], label_locs: list[str]) -> bool:
    for t in tool_locs:
        tf, tl = parse_loc(t)
        for lab in label_locs:
            lf, ll = parse_loc(lab)
            if tf == lf and abs(tl - ll) <= LINE_WINDOW:
                return True
    return False


def norm_version(v: str | None) -> str | None:
    if v is None:
        return None
    return v.strip().lstrip("=").strip().strip("/").lower() or None


def match(tool: list[dict], labels: list[dict], forbidden: set[tuple[str, str]] = frozenset()
          ) -> tuple[list[dict], list[dict], list[dict]]:
    pairs, used_t, used_l = [], set(), set()
    tool_locs = [[e["location"] for e in c["evidence"]] for c in tool]
    label_locs = [[e["location"] for e in c["evidence"]] for c in labels]
    rules = [
        ("name", lambda i, j: norm(tool[i]["canonical_name"]) == norm(labels[j]["canonical_name"])),
        ("evidence", lambda i, j: overlap(tool_locs[i], label_locs[j])),
        ("provider", lambda i, j: provider(tool[i]["canonical_name"]) == provider(labels[j]["canonical_name"])),
    ]
    for how, ok in rules:
        for j in range(len(labels)):
            if j in used_l:
                continue
            for i in range(len(tool)):
                if (tool[i]["canonical_name"], labels[j]["canonical_name"]) in forbidden:
                    continue
                if i not in used_t and ok(i, j):
                    pairs.append({"tool": i, "label": j, "how": how})
                    used_t.add(i)
                    used_l.add(j)
                    break
    fps = [i for i in range(len(tool)) if i not in used_t]
    fns = [j for j in range(len(labels)) if j not in used_l]
    return pairs, fps, fns


def prf(tp: int, n_tool: int, n_label: int) -> tuple[float, float, float]:
    p = tp / n_tool if n_tool else (1.0 if n_label == 0 else 0.0)
    r = tp / n_label if n_label else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def forbidden_pairs(repo: str) -> set[tuple[str, str]]:
    adj = load(HERE / "results" / "match_adjudication.json", {"forbidden_pairs": []})
    pairs = {(f["tool"], f["label"]) for f in adj["forbidden_pairs"] if f["repo"] == repo}
    labels = load(HERE / "labels" / f"{repo}.json", {}).get("components", [])
    for name in adj.get("forbidden_tool_names", []):  # placeholder names never match a named service
        pairs |= {(name, lab["canonical_name"]) for lab in labels}
    return pairs



def score_one(repo: str, mode: str) -> dict | None:
    run = HERE / "runs" / repo / mode
    if not (run / "components.json").exists():
        return None
    tool = load(run / "components.json", {})["components"]
    labels = load(HERE / "labels" / f"{repo}.json", {})["components"]
    log = load(run / "run_log.json", {})
    prep = load(run / "work" / "prepare_stats.json", {})
    pairs, fps, fns = match(tool, labels, forbidden_pairs(repo))
    tp = len(pairs)
    strict = sum(p["how"] == "name" for p in pairs)
    api = [0, 0]
    pkg = [0, 0]
    for pr in pairs:
        t, lab = tool[pr["tool"]], labels[pr["label"]]
        if lab["version"]["api"]:
            api[1] += 1
            api[0] += norm_version(t.get("api_version")) == norm_version(lab["version"]["api"])
        if lab["version"]["package"]:
            pkg[1] += 1
            pkg[0] += norm_version(t.get("package_version")) == norm_version(lab["version"]["package"])
    cand = prep.get("candidates", 0) or 0
    row = {
        "set": SET_OF[repo], "repo": repo, "mode": mode,
        "labels": len(labels), "tool": len(tool), "tp": tp, "fp": len(fps), "fn": len(fns),
        "strict_tp": strict, "api_ok": api[0], "api_n": api[1], "pkg_ok": pkg[0], "pkg_n": pkg[1],
        "candidates": cand,
        "static_n": prep.get("static_resolved", 0) + prep.get("folded", 0),
        "llm_n": prep.get("llm_call_inputs", 0) + prep.get("llm_package_call_sites", 0),
        "llm_questions": log.get("llm_questions", 0),
        "tokens_in": log.get("tokens_cold_run", {}).get("input_tokens", 0),
        "tokens_out": log.get("tokens_cold_run", {}).get("output_tokens", 0),
        "cost_usd": round(log.get("cost_usd_cold_run", 0.0), 4),
        "invalid": log.get("invalid_answers", 0),
        "model": log.get("model"),
    }
    detail = {
        "repo": repo, "mode": mode,
        "tp": [{"tool": tool[x["tool"]]["canonical_name"], "label": labels[x["label"]]["canonical_name"], "how": x["how"],
                "tool_evidence": [e["location"] for e in tool[x["tool"]]["evidence"]][:5],
                "label_evidence": [e["location"] for e in labels[x["label"]]["evidence"]]} for x in pairs],
        "fp": [{"tool": tool[i]["canonical_name"], "hosting": tool[i]["hosting"],
                "evidence": [{k: e.get(k) for k in ("location", "callee", "found_by", "scan_kind")} for e in tool[i]["evidence"]][:8],
                "n_evidence": len(tool[i]["evidence"])} for i in fps],
        "fn": [{"label": labels[j]["canonical_name"], "python_evidence": labels[j]["python_evidence"],
                "evidence": labels[j]["evidence"], "notes": labels[j]["notes"]} for j in fns],
    }
    return {"row": row, "detail": detail}


def finish(row: dict) -> dict:
    p, r, f = prf(row["tp"], row["tool"], row["labels"])
    sp, sr, sf = prf(row["strict_tp"], row["tool"], row["labels"])
    vn = row["api_n"] + row["pkg_n"]
    return row | {
        "precision": p, "recall": r, "f1": f, "strict_f1": sf,
        "name_accuracy": round(row["strict_tp"] / row["tp"], 3) if row["tp"] else None,
        "version_accuracy": round((row["api_ok"] + row["pkg_ok"]) / vn, 3) if vn else None,
        "pct_llm": round(100 * row["llm_n"] / row["candidates"], 1) if row["candidates"] else 0.0,
    }


def micro(rows: list[dict], label: str, mode: str) -> dict:
    keys = ["labels", "tool", "tp", "fp", "fn", "strict_tp", "api_ok", "api_n", "pkg_ok", "pkg_n", "candidates",
            "static_n", "llm_n", "llm_questions", "tokens_in", "tokens_out", "invalid"]
    agg = {k: sum(r[k] for r in rows) for k in keys}
    return {"set": label, "repo": f"ALL {label}", "mode": mode, **agg,
            "cost_usd": round(sum(r["cost_usd"] for r in rows), 4), "model": rows[0]["model"]}


def write_detail(d: dict) -> str:
    out = [f"# {d['repo']} — {d['mode']}", "", f"TP {len(d['tp'])} · FP {len(d['fp'])} · FN {len(d['fn'])}", "",
           "## True positives", "", "| tool | label | matched by | tool evidence | label evidence |", "|---|---|---|---|---|"]
    out += [f"| `{t['tool']}` | `{t['label']}` | {t['how']} | {', '.join(t['tool_evidence'])} | {', '.join(t['label_evidence'])} |"
            for t in d["tp"]]
    out += ["", "## False positives (tool only)", "", "| tool | hosting | evidence (location · callee · route) |", "|---|---|---|"]
    for t in d["fp"]:
        ev = "; ".join(f"{e['location']} · {e['callee']} · {e['scan_kind']}" for e in t["evidence"])
        more = f" …(+{t['n_evidence'] - 8})" if t["n_evidence"] > 8 else ""
        out.append(f"| `{t['tool']}` | {t['hosting']} | {ev}{more} |")
    out += ["", "## False negatives (label only)", "", "| label | python evidence | evidence | label notes |", "|---|---|---|---|"]
    out += [f"| `{t['label']}` | {t['python_evidence']} | {'; '.join(e['location'] for e in t['evidence'])} | {t['notes'][:200]} |"
            for t in d["fn"]]
    return "\n".join(out) + "\n"


def main() -> None:
    res = HERE / "results"
    (res / "per_repo").mkdir(parents=True, exist_ok=True)
    rows, details = [], []
    for mode in MODES:
        mode_rows = []
        for repo in REPOS:
            s = score_one(repo, mode)
            if s:
                mode_rows.append(s["row"])
                details.append(s["detail"])
                (res / "per_repo" / f"{repo}__{mode}.md").write_text(write_detail(s["detail"]))
        rows += [finish(r) for r in mode_rows]
        for label in ("dev", "heldout"):
            sub = [r for r in mode_rows if r["set"] == label]
            if sub:
                rows.append(finish(micro(sub, label, mode)))
        if len({r["set"] for r in mode_rows}) > 1:
            rows.append(finish(micro(mode_rows, "all", mode)))
    if not rows:
        raise SystemExit("no runs found under benchmark/runs/")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    (res / "results.csv").write_text(buf.getvalue())
    md = ["# depscan benchmark results", "",
          f"Model per row in results.csv. Matching: name → evidence (±{LINE_WINDOW} lines) → provider, with adjudication.", "",
          "| set | repo | mode | labels | tool | TP | FP | FN | P | R | **F1** | strict F1 | name acc | versions | % LLM | LLM questions | cost $ (cold) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        b = "**" if r["repo"].startswith("ALL") else ""
        na = "-" if r["name_accuracy"] is None else f"{r['name_accuracy']:.2f}"
        md.append(f"| {r['set']} | {b}{r['repo']}{b} | {r['mode']} | {r['labels']} | {r['tool']} | {r['tp']} | {r['fp']} | {r['fn']} | "
                  f"{r['precision']:.2f} | {r['recall']:.2f} | {b}{r['f1']:.2f}{b} | {r['strict_f1']:.2f} | {na} | "
                  f"{r['api_ok'] + r['pkg_ok']}/{r['api_n'] + r['pkg_n']} | {r['pct_llm']} | {r['llm_questions']} | {r['cost_usd']} |")
    (res / "results.md").write_text("\n".join(md) + "\n")
    (res / "matches.json").write_text(json.dumps(details, indent=2) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
