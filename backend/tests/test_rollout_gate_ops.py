# ruff: noqa: S101
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "rollout_gate_ops.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("rollout_gate_ops", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


@dataclass
class _FakeActionsApi:
    def __init__(self) -> None:
        self.secret_writes: list[tuple[str, str]] = []
        self.dispatch_calls: list[dict[str, str]] = []

    def set_secret(self, name: str, value: str) -> None:
        self.secret_writes.append((name, value))

    def dispatch_publish_workflow(self, *, gate_only: bool, allow_skipped_gate: bool) -> int:
        self.dispatch_calls.append(
            {
                "gate_only": str(gate_only).lower(),
                "allow_skipped_gate": str(allow_skipped_gate).lower(),
            }
        )
        return 123


def test_parse_health_urls_normalizes_and_deduplicates() -> None:
    module = _load_module()
    parsed = module.parse_health_urls(
        [
            "http://a/health, http://a/health ,http://b/readyz",
            "https://c/status",
            "",
        ]
    )
    assert parsed == ("http://a/health", "http://b/readyz", "https://c/status")


def test_parse_health_urls_rejects_invalid_protocols() -> None:
    module = _load_module()
    try:
        module.parse_health_urls(["ftp://bad.example/health"])
    except ValueError as exc:
        assert "http" in str(exc).lower()
    else:  # pragma: no cover - defensive branch
        raise AssertionError("Expected ValueError")


def test_execute_config_sets_health_and_rollback_and_dispatch() -> None:
    module = _load_module()
    cfg = module.RolloutOpsConfig(
        health_urls=("http://76.13.106.100:8100/readyz", "http://76.13.106.100:3100"),
        rollback_command="echo rollback",
        update_rollback=True,
        dispatch_gate_only=True,
        allow_skipped_gate=False,
    )
    api = _FakeActionsApi()

    result = module.execute_config(cfg, api)

    assert result["health_urls_count"] == 2
    assert result["rollback_updated"] is True
    assert result["dispatch_run_id"] == 123
    assert (
        "RUNTIME_HEALTH_URLS",
        "http://76.13.106.100:8100/readyz,http://76.13.106.100:3100",
    ) in api.secret_writes
    assert ("RUNTIME_ROLLBACK_COMMAND", "echo rollback") in api.secret_writes
    assert api.dispatch_calls == [{"gate_only": "true", "allow_skipped_gate": "false"}]


def test_execute_config_skips_rollback_update_when_not_requested() -> None:
    module = _load_module()
    cfg = module.RolloutOpsConfig(
        health_urls=("http://76.13.106.100:8100/readyz",),
        rollback_command="",
        update_rollback=False,
        dispatch_gate_only=False,
        allow_skipped_gate=False,
    )
    api = _FakeActionsApi()

    result = module.execute_config(cfg, api)

    assert result["rollback_updated"] is False
    assert result["dispatch_run_id"] is None
    assert api.secret_writes == [
        ("RUNTIME_HEALTH_URLS", "http://76.13.106.100:8100/readyz"),
    ]
    assert api.dispatch_calls == []


def test_select_new_run_id_skips_previous_latest_run() -> None:
    module = _load_module()
    runs = [{"id": 1001}, {"id": 1000}, {"id": 999}]

    selected = module.select_new_run_id(runs, previous_run_id=1001)

    assert selected == 1000


def test_select_new_run_id_returns_none_when_no_new_runs() -> None:
    module = _load_module()
    runs = [{"id": 77}]

    selected = module.select_new_run_id(runs, previous_run_id=77)

    assert selected is None


def test_select_new_run_id_respects_not_before_timestamp() -> None:
    module = _load_module()
    runs = [
        {"id": 11, "created_at": "2026-02-27T05:00:00Z"},
        {"id": 10, "created_at": "2026-02-27T04:59:59Z"},
    ]

    selected = module.select_new_run_id(runs, previous_run_id=None, not_before_epoch=1772168401.0)

    assert selected is None
