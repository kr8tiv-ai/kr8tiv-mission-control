# ruff: noqa: S101
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "rollout_health_gate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("rollout_health_gate", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_parse_urls_normalizes_and_deduplicates() -> None:
    module = _load_module()
    parsed = module.parse_urls(" http://a/health , http://b/readyz, ,http://a/health ")
    assert parsed == ("http://a/health", "http://b/readyz")


def test_run_health_gate_skips_when_urls_not_configured() -> None:
    module = _load_module()
    config = module.GateConfig(urls=(), attempts=2)
    result = module.run_health_gate(config)

    assert result["status"] == "skipped"
    assert result["status_reason"] == "no_urls_configured"
    assert result["rollback"]["attempted"] is False
    assert result["attempts"] == []


def test_run_health_gate_retries_until_success() -> None:
    module = _load_module()
    calls: list[str] = []
    sleeps: list[float] = []

    def _probe(url: str, timeout_seconds: float) -> dict:
        calls.append(url)
        if len(calls) <= 2:
            return {
                "ok": False,
                "status_code": None,
                "detail": "timeout",
                "elapsed_ms": 1,
            }
        return {
            "ok": True,
            "status_code": 200,
            "detail": "ok",
            "elapsed_ms": 1,
        }

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)

    config = module.GateConfig(
        urls=("http://api/health",),
        attempts=3,
        sleep_seconds=2.5,
        timeout_seconds=0.5,
    )
    result = module.run_health_gate(config, probe_fn=_probe, sleep_fn=_sleep)

    assert result["status"] == "passed"
    assert len(result["attempts"]) == 3
    assert sleeps == [2.5, 2.5]


def test_run_health_gate_triggers_rollback_on_failure() -> None:
    module = _load_module()

    def _probe(_url: str, timeout_seconds: float) -> dict:
        return {
            "ok": False,
            "status_code": None,
            "detail": f"timeout:{timeout_seconds}",
            "elapsed_ms": 1,
        }

    def _run_command(command: str, timeout_seconds: int) -> dict:
        return {
            "attempted": True,
            "command": command,
            "timeout_seconds": timeout_seconds,
            "exit_code": 0,
            "succeeded": True,
            "stdout": "rolled back",
            "stderr": "",
        }

    config = module.GateConfig(
        urls=("http://api/health",),
        attempts=2,
        rollback_on_fail=True,
        rollback_command="echo rollback",
        rollback_timeout_seconds=60,
    )
    result = module.run_health_gate(config, probe_fn=_probe, run_command_fn=_run_command)

    assert result["status"] == "failed"
    assert result["rollback"]["attempted"] is True
    assert result["rollback"]["succeeded"] is True
    assert result["rollback"]["command"] == "echo rollback"


def test_to_env_lines_exposes_gate_summary() -> None:
    module = _load_module()
    payload = {
        "status": "failed",
        "status_reason": "probe_failures",
        "failed_urls": ["http://api/health"],
        "rollback": {
            "attempted": True,
            "succeeded": False,
            "exit_code": 2,
        },
        "attempts": [1, 2],
    }
    env_lines = module.to_env_lines(payload)
    assert "ROLLOUT_GATE_STATUS=failed" in env_lines
    assert "ROLLOUT_GATE_STATUS_REASON=probe_failures" in env_lines
    assert "ROLLOUT_GATE_FAILED_URL_COUNT=1" in env_lines
    assert "ROLLOUT_GATE_ROLLBACK_ATTEMPTED=true" in env_lines
    assert "ROLLOUT_GATE_ROLLBACK_SUCCEEDED=false" in env_lines
    assert "ROLLOUT_GATE_ROLLBACK_EXIT_CODE=2" in env_lines


def test_compute_exit_code_respects_fail_on_skipped_policy() -> None:
    module = _load_module()

    assert module.compute_exit_code("passed", fail_on_skipped=True) == 0
    assert module.compute_exit_code("failed", fail_on_skipped=False) == 1
    assert module.compute_exit_code("skipped", fail_on_skipped=False) == 0
    assert module.compute_exit_code("skipped", fail_on_skipped=True) == 1
