"""Board-scoped continuity probes for agent heartbeat and runtime reachability."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import col, select

from app.core.time import utcnow
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.services.openclaw.constants import OFFLINE_AFTER
from app.services.openclaw.db_service import OpenClawDBService
from app.services.openclaw.gateway_resolver import gateway_client_config
from app.services.openclaw.gateway_rpc import OpenClawGatewayError, openclaw_call

ContinuityState = Literal["alive", "stale", "unreachable"]
RuntimeSessionKeysFetcher = Callable[[Gateway], Awaitable[set[str]]]


@dataclass(frozen=True, slots=True)
class AgentContinuityItem:
    """Per-agent continuity classification details."""

    agent_id: UUID
    agent_name: str
    board_id: UUID | None
    status: str
    continuity: ContinuityState
    continuity_reason: str
    runtime_session_id: str | None
    runtime_reachable: bool
    last_seen_at: datetime | None
    heartbeat_age_seconds: int | None


@dataclass(frozen=True, slots=True)
class AgentContinuityReport:
    """Board-level continuity snapshot for automation and operators."""

    board_id: UUID
    generated_at: datetime
    runtime_error: str | None
    counts: dict[str, int]
    agents: list[AgentContinuityItem]


def _as_object_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, (str, bytes, dict)):
        return []
    if isinstance(value, Iterable):
        return list(value)
    return []


def _extract_session_keys(payload: object) -> set[str]:
    if isinstance(payload, dict):
        raw_items = _as_object_list(payload.get("sessions"))
    else:
        raw_items = _as_object_list(payload)
    keys: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        key = raw.get("key")
        if isinstance(key, str) and key.strip():
            keys.add(key.strip())
    return keys


def _heartbeat_age_seconds(
    *,
    now: datetime,
    last_seen_at: datetime | None,
) -> int | None:
    if last_seen_at is None:
        return None
    delta = now - last_seen_at
    return max(int(delta.total_seconds()), 0)


def _is_stale(*, heartbeat_age_seconds: int | None) -> bool:
    if heartbeat_age_seconds is None:
        return True
    return heartbeat_age_seconds > int(OFFLINE_AFTER.total_seconds())


class AgentContinuityService(OpenClawDBService):
    """Compute continuity status for all agents assigned to a board."""

    def __init__(
        self,
        session,
        *,
        runtime_session_keys_fetcher: RuntimeSessionKeysFetcher | None = None,
    ) -> None:
        super().__init__(session)
        self._runtime_session_keys_fetcher = runtime_session_keys_fetcher

    async def fetch_runtime_session_keys(self, gateway: Gateway) -> set[str]:
        """Fetch currently reachable session keys from the gateway runtime."""
        if self._runtime_session_keys_fetcher is not None:
            return await self._runtime_session_keys_fetcher(gateway)
        payload = await openclaw_call("sessions.list", config=gateway_client_config(gateway))
        return _extract_session_keys(payload)

    async def _board_or_404(self, *, board_id: UUID) -> Board:
        board = await Board.objects.by_id(board_id).first(self.session)
        if board is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )
        return board

    async def _board_gateway(self, *, board: Board) -> Gateway | None:
        if board.gateway_id is None:
            return None
        return await Gateway.objects.by_id(board.gateway_id).first(self.session)

    async def snapshot_for_board(self, *, board_id: UUID) -> AgentContinuityReport:
        """Build a board-level continuity report with liveness and reachability."""
        board = await self._board_or_404(board_id=board_id)
        statement = (
            select(Agent)
            .where(col(Agent.board_id) == board.id)
            .order_by(col(Agent.created_at).asc())
        )
        agents = list(await self.session.exec(statement))

        runtime_session_keys: set[str] = set()
        runtime_error: str | None = None
        gateway = await self._board_gateway(board=board)
        if gateway is None:
            runtime_error = "Board gateway is not configured."
        else:
            try:
                runtime_session_keys = await self.fetch_runtime_session_keys(gateway)
            except (HTTPException, OpenClawGatewayError, OSError, RuntimeError, ValueError) as exc:
                runtime_error = str(exc)

        now = utcnow()
        counts = {"alive": 0, "stale": 0, "unreachable": 0}
        continuity_items: list[AgentContinuityItem] = []

        for agent in agents:
            session_id = (agent.openclaw_session_id or "").strip() or None
            heartbeat_age = _heartbeat_age_seconds(now=now, last_seen_at=agent.last_seen_at)
            stale = _is_stale(heartbeat_age_seconds=heartbeat_age)

            runtime_reachable = True
            continuity_reason = "healthy"
            if runtime_error:
                runtime_reachable = False
                continuity_reason = "runtime_unavailable"
            elif session_id is None:
                runtime_reachable = False
                continuity_reason = "runtime_session_missing"
            elif session_id not in runtime_session_keys:
                runtime_reachable = False
                continuity_reason = "runtime_session_unreachable"
            elif stale:
                continuity_reason = (
                    "heartbeat_missing"
                    if heartbeat_age is None
                    else "heartbeat_stale"
                )

            continuity: ContinuityState
            if not runtime_reachable:
                continuity = "unreachable"
            elif stale:
                continuity = "stale"
            else:
                continuity = "alive"

            counts[continuity] += 1
            continuity_items.append(
                AgentContinuityItem(
                    agent_id=agent.id,
                    agent_name=agent.name,
                    board_id=agent.board_id,
                    status=agent.status,
                    continuity=continuity,
                    continuity_reason=continuity_reason,
                    runtime_session_id=session_id,
                    runtime_reachable=runtime_reachable,
                    last_seen_at=agent.last_seen_at,
                    heartbeat_age_seconds=heartbeat_age,
                )
            )

        return AgentContinuityReport(
            board_id=board.id,
            generated_at=now,
            runtime_error=runtime_error,
            counts=counts,
            agents=continuity_items,
        )
