"""Owner-channel alert routing for runtime recovery incidents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.logging import get_logger
from app.services.channel_ingress import is_owner_alert_channel_enabled

if TYPE_CHECKING:
    from app.models.recovery_incidents import RecoveryIncident
    from app.models.recovery_policies import RecoveryPolicy

logger = get_logger(__name__)

ChannelSender = Callable[..., Awaitable[bool]]
UISink = Callable[..., Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class RecoveryAlertResult:
    """Result envelope for channel routing attempts."""

    channel: str
    delivered: bool
    attempted_channels: list[str]
    message: str


async def _noop_channel_sender(*, incident: "RecoveryIncident", message: str) -> bool:
    del incident, message
    return False


async def _noop_ui_sink(*, incident: "RecoveryIncident", message: str) -> bool:
    del incident, message
    return False


class RecoveryAlertService:
    """Route recovery incidents to owner channels with deterministic fallback."""

    def __init__(
        self,
        *,
        send_telegram: ChannelSender | None = None,
        send_whatsapp: ChannelSender | None = None,
        ui_sink: UISink | None = None,
        rollout_phase: str | None = None,
    ) -> None:
        self._send_telegram = send_telegram or _noop_channel_sender
        self._send_whatsapp = send_whatsapp or _noop_channel_sender
        self._ui_sink = ui_sink or _noop_ui_sink
        self._rollout_phase = (rollout_phase or settings.channel_rollout_phase).strip().lower()

    @staticmethod
    def render_alert_message(*, incident: "RecoveryIncident") -> str:
        """Render a concise owner-facing incident alert message."""
        return (
            "AGENT RECOVERY ALERT\n"
            f"Incident: {incident.id}\n"
            f"Board: {incident.board_id}\n"
            f"Agent: {incident.agent_id}\n"
            f"Status: {incident.status}\n"
            f"Reason: {incident.reason}\n"
            f"Action: {incident.action or 'none'}\n"
            f"Attempts: {incident.attempts}"
        )

    async def _try_sender(
        self,
        *,
        sender: ChannelSender,
        incident: "RecoveryIncident",
        message: str,
    ) -> bool:
        try:
            return bool(await sender(incident=incident, message=message))
        except Exception as exc:  # pragma: no cover - defensive runtime path
            logger.warning(
                "recovery.alert.delivery_failed",
                extra={
                    "incident_id": str(incident.id),
                    "board_id": str(incident.board_id),
                    "agent_id": str(incident.agent_id),
                    "error": str(exc),
                },
            )
            return False

    async def route_incident_alert(
        self,
        *,
        incident: "RecoveryIncident",
        policy: "RecoveryPolicy",
    ) -> RecoveryAlertResult:
        """Route incident alert to Telegram/WhatsApp, then fallback to UI sink."""
        message = self.render_alert_message(incident=incident)
        attempted: list[str] = []

        if policy.alert_telegram and is_owner_alert_channel_enabled(
            channel="telegram",
            phase=self._rollout_phase,
        ):
            attempted.append("telegram")
            if await self._try_sender(sender=self._send_telegram, incident=incident, message=message):
                return RecoveryAlertResult(
                    channel="telegram",
                    delivered=True,
                    attempted_channels=attempted,
                    message=message,
                )

        if policy.alert_whatsapp and is_owner_alert_channel_enabled(
            channel="whatsapp",
            phase=self._rollout_phase,
        ):
            attempted.append("whatsapp")
            if await self._try_sender(sender=self._send_whatsapp, incident=incident, message=message):
                return RecoveryAlertResult(
                    channel="whatsapp",
                    delivered=True,
                    attempted_channels=attempted,
                    message=message,
                )

        if policy.alert_ui and is_owner_alert_channel_enabled(channel="ui", phase=self._rollout_phase):
            attempted.append("ui")
            delivered = await self._try_sender(sender=self._ui_sink, incident=incident, message=message)
            return RecoveryAlertResult(
                channel="ui",
                delivered=delivered,
                attempted_channels=attempted,
                message=message,
            )

        return RecoveryAlertResult(
            channel="none",
            delivered=False,
            attempted_channels=attempted,
            message=message,
        )


__all__ = ["RecoveryAlertService", "RecoveryAlertResult"]
