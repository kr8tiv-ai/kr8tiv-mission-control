# ruff: noqa: S101
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "rollback_incident_hook.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("rollback_incident_hook", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_parse_probe_urls_normalizes_and_deduplicates() -> None:
    module = _load_module()

    parsed = module.parse_probe_urls(" http://a/health, http://b/readyz , http://a/health ")

    assert parsed == ("http://a/health", "http://b/readyz")


def test_build_issue_payload_includes_run_url_and_reason() -> None:
    module = _load_module()

    payload = module.build_issue_payload(
        owner="kr8tiv-ai",
        repo="kr8tiv-mission-control",
        run_id="22476038198",
        workflow_name="Publish Mission Control Images",
        gate_status="failed",
        status_reason="probe_failures",
        probe_urls=("http://76.13.106.100:8100/readyz", "http://76.13.106.100:3100"),
    )

    assert "title" in payload
    assert "22476038198" in payload["title"]
    assert "body" in payload
    assert "probe_failures" in payload["body"]
    assert "https://github.com/kr8tiv-ai/kr8tiv-mission-control/actions/runs/22476038198" in payload["body"]
    assert "http://76.13.106.100:8100/readyz" in payload["body"]
    assert payload["labels"] == ["incident", "rollout-gate"]
