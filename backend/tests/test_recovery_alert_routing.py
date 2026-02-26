# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.recovery_incidents import RecoveryIncident
from app.models.recovery_policies import RecoveryPolicy
from app.services.runtime.recovery_alerts import RecoveryAlertService


def _incident() -> RecoveryIncident:
    return RecoveryIncident(
        organization_id=uuid4(),
        board_id=uuid4(),
        agent_id=uuid4(),
        status="failed",
        reason="runtime_session_unreachable",
        action=None,
        attempts=2,
    )


def _policy(*, telegram: bool = True, whatsapp: bool = True, ui: bool = True) -> RecoveryPolicy:
    return RecoveryPolicy(
        organization_id=uuid4(),
        alert_telegram=telegram,
        alert_whatsapp=whatsapp,
        alert_ui=ui,
    )


@pytest.mark.asyncio
async def test_recovery_alert_prefers_enabled_owner_channels() -> None:
    incident = _incident()
    policy = _policy(telegram=True, whatsapp=True, ui=True)
    sent_channels: list[str] = []

    async def _send_telegram(*, incident: RecoveryIncident, message: str) -> bool:
        del incident, message
        sent_channels.append("telegram")
        return True

    async def _send_whatsapp(*, incident: RecoveryIncident, message: str) -> bool:
        del incident, message
        sent_channels.append("whatsapp")
        return True

    service = RecoveryAlertService(
        send_telegram=_send_telegram,
        send_whatsapp=_send_whatsapp,
        rollout_phase="phase2",
    )
    result = await service.route_incident_alert(incident=incident, policy=policy)

    assert result.channel == "telegram"
    assert result.delivered is True
    assert result.attempted_channels == ["telegram"]
    assert sent_channels == ["telegram"]


@pytest.mark.asyncio
async def test_whatsapp_respects_phase_gates() -> None:
    incident = _incident()
    policy = _policy(telegram=False, whatsapp=True, ui=True)
    sent_channels: list[str] = []

    async def _send_whatsapp(*, incident: RecoveryIncident, message: str) -> bool:
        del incident, message
        sent_channels.append("whatsapp")
        return True

    ui_messages: list[str] = []

    async def _ui_sink(*, incident: RecoveryIncident, message: str) -> bool:
        del incident
        ui_messages.append(message)
        return True

    service = RecoveryAlertService(
        send_whatsapp=_send_whatsapp,
        ui_sink=_ui_sink,
        rollout_phase="phase1",
    )
    result = await service.route_incident_alert(incident=incident, policy=policy)

    assert result.channel == "ui"
    assert result.delivered is True
    assert "whatsapp" not in result.attempted_channels
    assert sent_channels == []
    assert len(ui_messages) == 1


@pytest.mark.asyncio
async def test_ui_alert_fallback_when_channel_delivery_fails() -> None:
    incident = _incident()
    policy = _policy(telegram=True, whatsapp=True, ui=True)
    sent_channels: list[str] = []
    ui_messages: list[str] = []

    async def _send_telegram(*, incident: RecoveryIncident, message: str) -> bool:
        del incident, message
        sent_channels.append("telegram")
        return False

    async def _send_whatsapp(*, incident: RecoveryIncident, message: str) -> bool:
        del incident, message
        sent_channels.append("whatsapp")
        raise RuntimeError("delivery failed")

    async def _ui_sink(*, incident: RecoveryIncident, message: str) -> bool:
        del incident
        ui_messages.append(message)
        return True

    service = RecoveryAlertService(
        send_telegram=_send_telegram,
        send_whatsapp=_send_whatsapp,
        ui_sink=_ui_sink,
        rollout_phase="phase2",
    )
    result = await service.route_incident_alert(incident=incident, policy=policy)

    assert result.channel == "ui"
    assert result.delivered is True
    assert result.attempted_channels == ["telegram", "whatsapp", "ui"]
    assert sent_channels == ["telegram", "whatsapp"]
    assert len(ui_messages) == 1
