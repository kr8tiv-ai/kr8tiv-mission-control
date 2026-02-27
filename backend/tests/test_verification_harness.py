# ruff: noqa: S101
from __future__ import annotations

import pytest

from app.core.time import utcnow
from app.services.notebooklm_capability_gate import NotebookCapabilityGateResult
from app.services.runtime import verification_harness


def _route_paths() -> set[str]:
    return {
        "/health",
        "/readyz",
        "/api/v1/runtime/notebook/gate",
        "/api/v1/runtime/recovery/run",
    }


async def _ready_gate(**_kwargs) -> NotebookCapabilityGateResult:
    return NotebookCapabilityGateResult(
        state="ready",
        reason="ok",
        operator_message="ready",
        checked_at=utcnow(),
        selected_profile="default",
        notebook_count=1,
    )


async def _failing_probe(*, urls: tuple[str, ...]) -> tuple[bool, str]:
    assert urls == ("http://probe-a/health", "http://probe-b/readyz")
    return False, "failed:http://probe-a/health=timeout"


async def _passing_probe(*, urls: tuple[str, ...]) -> tuple[bool, str]:
    assert urls == ("http://probe-a/health", "http://probe-b/readyz")
    return True, "ok:2"


@pytest.mark.asyncio
async def test_external_probe_check_is_emitted_when_unconfigured(
    monkeypatch,
) -> None:
    monkeypatch.delenv("VERIFICATION_EXTERNAL_HEALTH_URLS", raising=False)
    monkeypatch.setattr(verification_harness, "evaluate_notebooklm_capability", _ready_gate)

    result = await verification_harness.run_verification_harness(route_paths=_route_paths())

    check = next((entry for entry in result.checks if entry.name == "external_health_probe"), None)
    assert check is not None
    assert check.required is False
    assert check.passed is True
    assert check.detail == "skipped:unconfigured"


@pytest.mark.asyncio
async def test_external_probe_check_fails_required_gate_when_probe_fails(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "VERIFICATION_EXTERNAL_HEALTH_URLS",
        "http://probe-a/health,http://probe-b/readyz",
    )
    monkeypatch.setattr(verification_harness, "evaluate_notebooklm_capability", _ready_gate)
    monkeypatch.setattr(verification_harness, "_probe_external_health", _failing_probe, raising=False)

    result = await verification_harness.run_verification_harness(route_paths=_route_paths())

    check = next((entry for entry in result.checks if entry.name == "external_health_probe"), None)
    assert check is not None
    assert check.required is True
    assert check.passed is False
    assert check.detail.startswith("failed:")
    assert result.all_passed is False
    assert result.required_failed == 1


@pytest.mark.asyncio
async def test_external_probe_check_passes_required_gate_when_probe_succeeds(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "VERIFICATION_EXTERNAL_HEALTH_URLS",
        "http://probe-a/health,http://probe-b/readyz",
    )
    monkeypatch.setattr(verification_harness, "evaluate_notebooklm_capability", _ready_gate)
    monkeypatch.setattr(verification_harness, "_probe_external_health", _passing_probe, raising=False)

    result = await verification_harness.run_verification_harness(route_paths=_route_paths())

    check = next((entry for entry in result.checks if entry.name == "external_health_probe"), None)
    assert check is not None
    assert check.required is True
    assert check.passed is True
    assert check.detail == "ok:2"
    assert result.all_passed is True
    assert result.required_failed == 0
