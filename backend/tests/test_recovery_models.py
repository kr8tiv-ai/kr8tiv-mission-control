# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

from app.models.recovery_incidents import RecoveryIncident
from app.models.recovery_policies import RecoveryPolicy


def test_recovery_policy_defaults_enable_autorestart_with_cooldown() -> None:
    policy = RecoveryPolicy(organization_id=uuid4())

    assert policy.enabled is True
    assert policy.stale_after_seconds == 900
    assert policy.max_restarts_per_hour == 3
    assert policy.cooldown_seconds == 300
    assert policy.alert_telegram is True
    assert policy.alert_whatsapp is True
    assert policy.alert_ui is True


def test_recovery_incident_status_lifecycle_fields_present() -> None:
    incident = RecoveryIncident(
        organization_id=uuid4(),
        board_id=uuid4(),
        agent_id=uuid4(),
        reason="stale_heartbeat",
    )

    assert incident.status == "detected"
    assert incident.reason == "stale_heartbeat"
    assert incident.action is None
    assert incident.attempts == 0
    assert incident.last_error is None
    assert incident.recovered_at is None
