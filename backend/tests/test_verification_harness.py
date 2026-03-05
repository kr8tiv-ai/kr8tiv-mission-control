# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.time import utcnow
from app.models.agent_persona_integrity import AgentPersonaIntegrity
from app.models.agents import Agent
from app.models.recovery_policies import RecoveryPolicy
from app.services.agent_continuity import AgentContinuityItem
from app.services.openclaw.gateway_compat import GatewayVersionCheckResult
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


async def _matrix_skipped(**_kwargs) -> tuple[
    verification_harness.VerificationCheckResult,
    verification_harness.VerificationCheckResult,
    list[verification_harness.AgentPointResult],
]:
    return (
        verification_harness.VerificationCheckResult(
            name="four_agent_harness_matrix",
            required=False,
            passed=True,
            detail="skipped:test",
        ),
        verification_harness.VerificationCheckResult(
            name="four_agent_supermemory_default",
            required=False,
            passed=True,
            detail="skipped:test",
        ),
        [],
    )


@pytest.mark.asyncio
async def test_external_probe_check_is_emitted_when_unconfigured(
    monkeypatch,
) -> None:
    monkeypatch.delenv("VERIFICATION_EXTERNAL_HEALTH_URLS", raising=False)
    monkeypatch.setattr(verification_harness, "evaluate_notebooklm_capability", _ready_gate)
    monkeypatch.setattr(verification_harness, "_evaluate_four_agent_matrix", _matrix_skipped)

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
    monkeypatch.setattr(verification_harness, "_evaluate_four_agent_matrix", _matrix_skipped)

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
    monkeypatch.setattr(verification_harness, "_evaluate_four_agent_matrix", _matrix_skipped)

    result = await verification_harness.run_verification_harness(route_paths=_route_paths())

    check = next((entry for entry in result.checks if entry.name == "external_health_probe"), None)
    assert check is not None
    assert check.required is True
    assert check.passed is True
    assert check.detail == "ok:2"
    assert result.all_passed is True
    assert result.required_failed == 0


def test_point1_requires_non_empty_identity_and_soul_templates() -> None:
    point = {
        "point_id": 1,
        "name": "IDENTITY_REGISTER",
        "agent_expectations": {
            "friday": {"role": "CMO & Executive Director"},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={"role": "CMO & Executive Director"},
        identity_template="",
        soul_template="",
    )

    result = verification_harness._evaluate_agent_point(agent=agent, point=point)

    assert result.passed is False
    assert "identity_template=false" in result.detail
    assert "soul_template=false" in result.detail


def test_point1_passes_with_role_and_templates_present() -> None:
    point = {
        "point_id": 1,
        "name": "IDENTITY_REGISTER",
        "agent_expectations": {
            "friday": {"role": "CMO & Executive Director"},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={"role": "CMO & Executive Director"},
        identity_template="# IDENTITY.md\n...",
        soul_template="# SOUL.md\n...",
    )

    result = verification_harness._evaluate_agent_point(agent=agent, point=point)

    assert result.passed is True


def _continuity_item(
    *,
    continuity: str = "alive",
    runtime_reachable: bool = True,
    runtime_session_id: str | None = "session-1",
    heartbeat_age_seconds: int | None = 30,
) -> AgentContinuityItem:
    return AgentContinuityItem(
        agent_id=uuid4(),
        agent_name="Friday",
        board_id=uuid4(),
        status="online",
        continuity=continuity,
        continuity_reason="healthy" if continuity == "alive" else "heartbeat_stale",
        runtime_session_id=runtime_session_id,
        runtime_reachable=runtime_reachable,
        last_seen_at=utcnow(),
        heartbeat_age_seconds=heartbeat_age_seconds,
    )


def _persona_integrity_row() -> AgentPersonaIntegrity:
    return AgentPersonaIntegrity(
        agent_id=uuid4(),
        soul_sha256="soul",
        user_sha256="user",
        identity_sha256="identity",
        heartbeat_sha256="heartbeat",
        agents_sha256="agents",
        drift_count=0,
        last_checked_at=utcnow(),
        last_drift_at=None,
        last_drift_fields=[],
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def _recovery_policy(*, cooldown_seconds: int = 300, alert_dedupe_seconds: int = 900) -> RecoveryPolicy:
    return RecoveryPolicy(
        organization_id=uuid4(),
        enabled=True,
        stale_after_seconds=900,
        max_restarts_per_hour=3,
        cooldown_seconds=cooldown_seconds,
        alert_dedupe_seconds=alert_dedupe_seconds,
        alert_telegram=True,
        alert_whatsapp=True,
        alert_ui=True,
    )


def _gateway_version(*, compatible: bool) -> GatewayVersionCheckResult:
    return GatewayVersionCheckResult(
        compatible=compatible,
        minimum_version="2026.3.2",
        current_version="2026.3.2" if compatible else "2026.2.23",
        message=None if compatible else "Gateway version 2026.2.23 is not supported.",
    )


def test_point1_requires_persona_integrity_baseline_when_runtime_evidence_is_available() -> None:
    point = {
        "point_id": 1,
        "name": "IDENTITY_REGISTER",
        "agent_expectations": {
            "friday": {"role": "CMO & Executive Director"},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={"role": "CMO & Executive Director"},
        identity_template="# IDENTITY.md\n...",
        soul_template="# SOUL.md\n...",
    )

    result = verification_harness._evaluate_agent_point(
        agent=agent,
        point=point,
        evidence=verification_harness.AgentVerificationEvidence(persona_integrity=None),
    )

    assert result.passed is False
    assert "persona_baseline=false" in result.detail


def test_point2_requires_alive_runtime_continuity_when_runtime_evidence_is_available() -> None:
    point = {
        "point_id": 2,
        "name": "HEALTH_HEARTBEAT",
        "agent_expectations": {
            "friday": {"max_timeout_seconds": 90},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        heartbeat_config={"every": "30m", "includeReasoning": False},
    )

    result = verification_harness._evaluate_agent_point(
        agent=agent,
        point=point,
        evidence=verification_harness.AgentVerificationEvidence(
            continuity=_continuity_item(continuity="stale", heartbeat_age_seconds=180),
        ),
    )

    assert result.passed is False
    assert "continuity=stale" in result.detail


def test_point6_requires_live_runtime_session_binding_when_runtime_evidence_is_available() -> None:
    point = {
        "point_id": 6,
        "name": "TASK_INTAKE",
        "agent_expectations": {
            "friday": {
                "assignment_authority": "owner_or_friday",
                "tools_profile": "coding",
                "tailscale_access": "required_on_spawn",
                "host_context_bootstrap": "required_on_spawn",
                "identity_bootstrap": "required_on_spawn",
            },
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={
            "assignment_authority": "owner_or_friday",
            "tools_profile": "coding",
            "tailscale_access": "required_on_spawn",
            "host_context_bootstrap": "required_on_spawn",
            "identity_bootstrap": "required_on_spawn",
        },
    )

    result = verification_harness._evaluate_agent_point(
        agent=agent,
        point=point,
        evidence=verification_harness.AgentVerificationEvidence(
            continuity=_continuity_item(runtime_session_id=None, runtime_reachable=False),
        ),
    )

    assert result.passed is False
    assert "runtime_session_bound=false" in result.detail


def test_point10_requires_recovery_policy_evidence() -> None:
    point = {
        "point_id": 10,
        "name": "AUTO_RECOVERY",
        "agent_expectations": {
            "friday": {"single_owner_recovery": True},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={
            "coordination_contract": "Execution starts only when assigned by Matt or Friday.",
        },
    )

    result = verification_harness._evaluate_agent_point(
        agent=agent,
        point=point,
        evidence=verification_harness.AgentVerificationEvidence(
            recovery_policy=_recovery_policy(cooldown_seconds=0, alert_dedupe_seconds=0),
        ),
    )

    assert result.passed is False
    assert "cooldown_seconds=0" in result.detail


def test_point14_requires_template_sync_route_and_runtime_binding() -> None:
    point = {
        "point_id": 14,
        "name": "CONFIG_HOT_RELOAD",
        "agent_expectations": {
            "friday": {"hot_reload": True},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={"hot_reload_contract": "Template sync applies canon at runtime."},
    )

    result = verification_harness._evaluate_agent_point(
        agent=agent,
        point=point,
        evidence=verification_harness.AgentVerificationEvidence(
            continuity=_continuity_item(),
        ),
        route_paths={"/health"},
    )

    assert result.passed is False
    assert "template_sync_route=false" in result.detail


def test_point15_uses_gateway_version_compatibility_evidence() -> None:
    point = {
        "point_id": 15,
        "name": "VERSION_SYNC",
        "agent_expectations": {
            "friday": {"version_sync": True},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={"version_sync_contract": "Gateway/runtime versions must stay aligned."},
    )

    result = verification_harness._evaluate_agent_point(
        agent=agent,
        point=point,
        evidence=verification_harness.AgentVerificationEvidence(
            gateway_version=_gateway_version(compatible=False),
        ),
    )

    assert result.passed is False
    assert "gateway_compatible=false" in result.detail


def test_point1_passes_with_persona_integrity_baseline() -> None:
    point = {
        "point_id": 1,
        "name": "IDENTITY_REGISTER",
        "agent_expectations": {
            "friday": {"role": "CMO & Executive Director"},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={"role": "CMO & Executive Director"},
        identity_template="# IDENTITY.md\n...",
        soul_template="# SOUL.md\n...",
    )

    result = verification_harness._evaluate_agent_point(
        agent=agent,
        point=point,
        evidence=verification_harness.AgentVerificationEvidence(
            persona_integrity=_persona_integrity_row(),
        ),
    )

    assert result.passed is True


def test_point15_passes_with_compatible_gateway_runtime() -> None:
    point = {
        "point_id": 15,
        "name": "VERSION_SYNC",
        "agent_expectations": {
            "friday": {"version_sync": True},
        },
    }
    agent = Agent(
        id=uuid4(),
        name="Friday",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        identity_profile={"version_sync_contract": "Gateway/runtime versions must stay aligned."},
    )

    result = verification_harness._evaluate_agent_point(
        agent=agent,
        point=point,
        evidence=verification_harness.AgentVerificationEvidence(
            gateway_version=_gateway_version(compatible=True),
        ),
    )

    assert result.passed is True
