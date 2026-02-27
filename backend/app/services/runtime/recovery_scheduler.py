"""Periodic board recovery sweep with alert dedupe suppression."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from sqlmodel import col, select

from app.models.boards import Board
from app.models.recovery_incidents import RecoveryIncident
from app.models.recovery_policies import RecoveryPolicy
from app.services.openclaw.db_service import OpenClawDBService
from app.services.runtime.recovery_alerts import RecoveryAlertResult, RecoveryAlertService
from app.services.runtime.recovery_engine import RecoveryEngine

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


class RecoveryEngineProtocol(Protocol):
    async def evaluate_board(self, *, board_id: UUID) -> list[RecoveryIncident]: ...


class RecoveryAlertProtocol(Protocol):
    async def route_incident_alert(
        self,
        *,
        incident: RecoveryIncident,
        policy: RecoveryPolicy,
    ) -> RecoveryAlertResult: ...


@dataclass(frozen=True, slots=True)
class RecoverySweepResult:
    board_count: int
    incident_count: int
    alerts_sent: int
    alerts_suppressed_dedupe: int
    alerts_skipped_status: int


class RecoveryScheduler(OpenClawDBService):
    """Execute one recovery sweep across boards and route deduped alerts."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        recovery_engine_factory: Callable[[AsyncSession], RecoveryEngineProtocol] | None = None,
        alert_service: RecoveryAlertProtocol | None = None,
    ) -> None:
        super().__init__(session)
        self._recovery_engine_factory = recovery_engine_factory or (lambda session: RecoveryEngine(session=session))
        self._alert_service = alert_service or RecoveryAlertService()

    async def _ensure_policy(self, *, organization_id: UUID) -> RecoveryPolicy:
        policy = await RecoveryPolicy.objects.filter_by(organization_id=organization_id).first(self.session)
        if policy is not None:
            return policy
        policy = RecoveryPolicy(organization_id=organization_id)
        await self.add_commit_refresh(policy)
        return policy

    async def _is_duplicate_alert(self, *, incident: RecoveryIncident, dedupe_seconds: int) -> bool:
        if dedupe_seconds <= 0:
            return False
        if incident.board_id is None or incident.agent_id is None:
            return False
        window_start = incident.detected_at - timedelta(seconds=dedupe_seconds)
        statement = (
            select(RecoveryIncident)
            .where(col(RecoveryIncident.board_id) == incident.board_id)
            .where(col(RecoveryIncident.agent_id) == incident.agent_id)
            .where(col(RecoveryIncident.status) == incident.status)
            .where(col(RecoveryIncident.reason) == incident.reason)
            .where(col(RecoveryIncident.detected_at) >= window_start)
            .where(col(RecoveryIncident.id) != incident.id)
            .order_by(col(RecoveryIncident.detected_at).desc())
            .limit(1)
        )
        return (await self.session.exec(statement)).first() is not None

    async def run_once(self) -> RecoverySweepResult:
        """Run one full board recovery sweep and route alerts with dedupe checks."""
        boards = (await self.session.exec(select(Board))).all()
        board_count = len(boards)
        incident_count = 0
        alerts_sent = 0
        alerts_suppressed_dedupe = 0
        alerts_skipped_status = 0

        policy_cache: dict[UUID, RecoveryPolicy] = {}
        for board in boards:
            engine = self._recovery_engine_factory(self.session)
            incidents = await engine.evaluate_board(board_id=board.id)
            incident_count += len(incidents)

            policy = policy_cache.get(board.organization_id)
            if policy is None:
                policy = await self._ensure_policy(organization_id=board.organization_id)
                policy_cache[board.organization_id] = policy

            for incident in incidents:
                if incident.status == "suppressed":
                    alerts_skipped_status += 1
                    continue
                if await self._is_duplicate_alert(
                    incident=incident,
                    dedupe_seconds=max(policy.alert_dedupe_seconds, 0),
                ):
                    alerts_suppressed_dedupe += 1
                    continue
                delivery = await self._alert_service.route_incident_alert(
                    incident=incident,
                    policy=policy,
                )
                if bool(getattr(delivery, "delivered", False)):
                    alerts_sent += 1

        return RecoverySweepResult(
            board_count=board_count,
            incident_count=incident_count,
            alerts_sent=alerts_sent,
            alerts_suppressed_dedupe=alerts_suppressed_dedupe,
            alerts_skipped_status=alerts_skipped_status,
        )


__all__ = ["RecoveryScheduler", "RecoverySweepResult"]
