"""Bounded automated recovery orchestration for stale/unreachable agents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import inspect
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import col, select

from app.core.time import utcnow
from app.models.agents import Agent
from app.models.boards import Board
from app.models.recovery_incidents import RecoveryIncident
from app.models.recovery_policies import RecoveryPolicy
from app.services.agent_continuity import (
    AgentContinuityReport,
    AgentContinuityService,
    continuity_requires_recovery,
)
from app.services.openclaw.db_service import OpenClawDBService

ContinuitySnapshotFetcher = Callable[..., Awaitable[AgentContinuityReport]]
RecoveryAction = Callable[..., Awaitable[tuple[bool, str]]]

_SUPPRESSED_STATUSES = {"suppressed"}
_ATTEMPT_STATUSES = {"recovering", "recovered", "failed"}


class RecoveryEngine(OpenClawDBService):
    """Evaluate continuity snapshots and create recovery incidents with guardrails."""

    def __init__(
        self,
        session,
        *,
        continuity_snapshot_fetcher: ContinuitySnapshotFetcher | None = None,
        recovery_action: RecoveryAction | None = None,
        force_heartbeat_resync: bool = False,
    ) -> None:
        super().__init__(session)
        self._continuity_snapshot_fetcher = continuity_snapshot_fetcher
        self._recovery_action = recovery_action
        self._force_heartbeat_resync = force_heartbeat_resync

    async def _board_or_404(self, *, board_id: UUID) -> Board:
        board = await Board.objects.by_id(board_id).first(self.session)
        if board is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )
        return board

    async def _snapshot_for_board(self, *, board_id: UUID) -> AgentContinuityReport:
        if self._continuity_snapshot_fetcher is not None:
            payload = self._continuity_snapshot_fetcher(board_id=board_id)
            if inspect.isawaitable(payload):
                return await payload
            return payload
        return await AgentContinuityService(self.session).snapshot_for_board(board_id=board_id)

    async def _recover_agent(self, *, board_id: UUID, agent_id: UUID, continuity_reason: str) -> tuple[bool, str]:
        if self._force_heartbeat_resync and continuity_reason in {"heartbeat_missing", "heartbeat_stale"}:
            agent = await Agent.objects.by_id(agent_id).first(self.session)
            if agent is not None and agent.board_id == board_id:
                now = utcnow()
                agent.status = "online"
                agent.last_seen_at = now
                agent.updated_at = now
                self.session.add(agent)
                return True, "forced_heartbeat_resync"
        if self._recovery_action is not None:
            return await self._recovery_action(
                board_id=board_id,
                agent_id=agent_id,
                continuity_reason=continuity_reason,
            )
        # Default action contract when no provider is injected.
        return True, "session_resync"

    async def _ensure_policy(self, *, organization_id: UUID) -> RecoveryPolicy:
        policy = await RecoveryPolicy.objects.filter_by(organization_id=organization_id).first(self.session)
        if policy is not None:
            return policy
        policy = RecoveryPolicy(organization_id=organization_id)
        await self.add_commit_refresh(policy)
        return policy

    async def _latest_incident(self, *, agent_id: UUID) -> RecoveryIncident | None:
        statement = (
            select(RecoveryIncident)
            .where(col(RecoveryIncident.agent_id) == agent_id)
            .order_by(col(RecoveryIncident.detected_at).desc())
            .limit(1)
        )
        return (await self.session.exec(statement)).first()

    async def _attempt_count_last_hour(self, *, agent_id: UUID, now) -> int:
        window_start = now - timedelta(hours=1)
        statement = (
            select(RecoveryIncident)
            .where(col(RecoveryIncident.agent_id) == agent_id)
            .where(col(RecoveryIncident.detected_at) >= window_start)
            .order_by(col(RecoveryIncident.detected_at).desc())
        )
        rows = (await self.session.exec(statement)).all()
        return sum(1 for row in rows if row.status in _ATTEMPT_STATUSES)

    async def evaluate_board(
        self,
        *,
        board_id: UUID,
        bypass_cooldown: bool = False,
    ) -> list[RecoveryIncident]:
        """Run continuity-based recovery evaluation and persist incident outcomes."""
        board = await self._board_or_404(board_id=board_id)
        policy = await self._ensure_policy(organization_id=board.organization_id)
        if not policy.enabled:
            return []

        report = await self._snapshot_for_board(board_id=board.id)
        now = utcnow()
        incidents: list[RecoveryIncident] = []

        for item in report.agents:
            if not continuity_requires_recovery(item.continuity):
                continue

            latest = await self._latest_incident(agent_id=item.agent_id)
            if latest is not None and not bypass_cooldown:
                cooldown_seconds = int((now - latest.detected_at).total_seconds())
                if cooldown_seconds < max(policy.cooldown_seconds, 0):
                    incident = RecoveryIncident(
                        organization_id=board.organization_id,
                        board_id=board.id,
                        agent_id=item.agent_id,
                        status="suppressed",
                        reason="cooldown_active",
                        action=None,
                        attempts=latest.attempts,
                        detected_at=now,
                    )
                    self.session.add(incident)
                    incidents.append(incident)
                    continue

            attempts_last_hour = await self._attempt_count_last_hour(agent_id=item.agent_id, now=now)
            if attempts_last_hour >= max(policy.max_restarts_per_hour, 0):
                incident = RecoveryIncident(
                    organization_id=board.organization_id,
                    board_id=board.id,
                    agent_id=item.agent_id,
                    status="suppressed",
                    reason="attempt_limit_exceeded",
                    action=None,
                    attempts=attempts_last_hour,
                    detected_at=now,
                )
                self.session.add(incident)
                incidents.append(incident)
                continue

            attempt_number = attempts_last_hour + 1
            try:
                ok, action = await self._recover_agent(
                    board_id=board.id,
                    agent_id=item.agent_id,
                    continuity_reason=item.continuity_reason,
                )
            except Exception as exc:  # pragma: no cover - explicit fallback for runtime failures
                incident = RecoveryIncident(
                    organization_id=board.organization_id,
                    board_id=board.id,
                    agent_id=item.agent_id,
                    status="failed",
                    reason=item.continuity_reason,
                    action=None,
                    attempts=attempt_number,
                    last_error=str(exc),
                    detected_at=now,
                )
                self.session.add(incident)
                incidents.append(incident)
                continue

            incident = RecoveryIncident(
                organization_id=board.organization_id,
                board_id=board.id,
                agent_id=item.agent_id,
                status="recovered" if ok else "failed",
                reason=item.continuity_reason,
                action=action,
                attempts=attempt_number,
                detected_at=now,
                recovered_at=now if ok else None,
                last_error=None if ok else "recovery_action_returned_false",
            )
            self.session.add(incident)
            incidents.append(incident)

        if incidents:
            await self.session.commit()
            for incident in incidents:
                await self.session.refresh(incident)
        return incidents


__all__ = ["RecoveryEngine", "ContinuitySnapshotFetcher", "RecoveryAction"]
