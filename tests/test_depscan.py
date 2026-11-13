"""Offline tests: no LLM, no network. Run with `pytest`."""

import json
from pathlib import Path

from depscan import aliases, classify
from depscan.cli import main
from depscan.pipeline import run

SAMPLE = Path(__file__).parent / "fixtures" / "sample_app"


def test_static_pipeline_finds_sdk_components(tmp_path):
    result = run(SAMPLE, tmp_path, mode="static", llm="none", log=lambda m: None)
    names = {c["canonical_name"] for c in result["components"]}
    assert {"openai/chat-completions", "redis/redis"} <= names
    openai = next(c for c in result["components"] if c["canonical_name"] == "openai/chat-completions")
    assert openai["package_version"] == "1.50.0"  # exact == pin
    assert (tmp_path / "report.md").read_text().startswith("# External dependencies")
    log = json.loads((tmp_path / "run_log.json").read_text())
    assert log["mode"] == "static" and log["api_calls"] == 0
    assert result["run_log"]["installed_versions_read"] is False  # never runs repo code by default


def test_static_mode_routes_unclear_calls_and_folds_inbound(tmp_path):
    run(SAMPLE, tmp_path, mode="static", llm="none", log=lambda m: None)
    unclear = json.loads((tmp_path / "work" / "scan" / "unclear.json").read_text())
    kinds = {u["unclear_kind"] for u in unclear}
    assert {"raw_http", "stdlib_client"} <= kinds  # requests.get + sqlite3.connect need the LLM
    folded = json.loads((tmp_path / "work" / "folded.json").read_text())
    assert folded["packages"].get("fastapi")  # inbound framework is set aside, not a component


def test_static_run_is_deterministic(tmp_path):
    run(SAMPLE, tmp_path / "a", mode="static", llm="none", log=lambda m: None)
    run(SAMPLE, tmp_path / "b", mode="static", llm="none", log=lambda m: None)
    assert (tmp_path / "a" / "components.json").read_text() == (tmp_path / "b" / "components.json").read_text()


def test_cli_dry_run_sends_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(classify, "auto_provider", lambda: "ollama")
    monkeypatch.setattr(classify, "provider_available", lambda name: (True, "test"))
    assert main([str(SAMPLE), "--out", str(tmp_path), "--dry-run"]) == 0
    assert "Nothing was sent" in capsys.readouterr().err
    assert not (tmp_path / "components.json").exists()


def test_cli_rejects_bad_path(capsys):
    assert main(["/no/such/repo", "--llm", "none"]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_classifier_retry_cache_and_version_guard():
    classify.selfcheck()


def test_aliases():
    assert aliases.sdk_component("boto3", "boto3.client", ["'s3'"]) == ("aws/s3", "cloud")
    assert aliases.sdk_component("pydantic", "pydantic.Field", []) is None
    assert aliases.normalize_name("Hugging Face/Hub") == "huggingface/hub"


def test_consolidate_merges_endpoint_names_but_not_unrelated_services():
    from collections import Counter

    from depscan.merge import consolidate

    def ev(*locs):
        return [{"location": loc} for loc in locs]

    groups = {
        "acme/events": ev("src/clients/acme.py:10"),
        "acme/markets": ev("src/clients/acme.py:20", "src/clients/acme.py:30"),
        "acme/other": ev("elsewhere/x.py:1"),          # same provider, different directory: kept apart
        "docker/engine": ev("env/docker.py:5"),
        "docker/hub": ev("env/docker.py:9"),               # different hosting: kept apart
        "aws/s3": ev("cloud/store.py:1"),
        "aws/sqs": ev("cloud/store.py:2"),                 # multi-product provider: kept apart
    }
    hosting = {n: Counter({"cloud": 1}) for n in groups} | {"docker/engine": Counter({"self-hosted": 1})}
    targets, versions = {n: Counter() for n in groups}, {n: Counter() for n in groups}
    merged = consolidate(groups, hosting, targets, versions)
    assert merged == {"acme/markets": ["acme/events", "acme/markets"]}
    assert set(groups) == {"acme/markets", "acme/other", "docker/engine", "docker/hub", "aws/s3", "aws/sqs"}
    assert len(groups["acme/markets"]) == 3
