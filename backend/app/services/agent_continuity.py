"""Board-scoped continuity probes for agent heartbeat and runtime reachability."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import col, select

from app.core.time import utcnow
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.services.openclaw.constants import stale_after_for_heartbeat_config
from app.services.openclaw.db_service import OpenClawDBService
from app.services.openclaw.gateway_resolver import gateway_client_config
from app.services.openclaw.gateway_rpc import OpenClawGatewayError, openclaw_call

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

ContinuityState = Literal["alive", "stale", "unreachable"]
RuntimeSessionKeysFetcher = Callable[[Gateway], Awaitable[set[str]]]
RECOVERY_CONTINUITIES: frozenset[ContinuityState] = frozenset({"stale", "unreachable"})
RuntimeSessionSnapshot = dict[str, datetime | None]
RuntimeSessionSnapshotFetcher = Callable[[Gateway], Awaitable[set[str] | RuntimeSessionSnapshot]]


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


def _coerce_runtime_updated_at(raw: object) -> datetime | None:
    if isinstance(raw, (int, float)):
        value = float(raw)
        # Gateway emits epoch milliseconds for updatedAt.
        if value > 1_000_000_000_000:
            value /= 1000.0
        if value <= 0:
            return None
        return datetime.fromtimestamp(value, tz=UTC).replace(tzinfo=None)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    return None


def _extract_runtime_sessions(payload: object) -> RuntimeSessionSnapshot:
    if isinstance(payload, dict):
        raw_items = _as_object_list(payload.get("sessions"))
    else:
        raw_items = _as_object_list(payload)
    sessions: RuntimeSessionSnapshot = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        key = raw.get("key")
        if isinstance(key, str) and key.strip():
            sessions[key.strip()] = _coerce_runtime_updated_at(raw.get("updatedAt"))
    return sessions


def _normalize_runtime_sessions(
    value: set[str] | RuntimeSessionSnapshot,
) -> RuntimeSessionSnapshot:
    if isinstance(value, dict):
        normalized: RuntimeSessionSnapshot = {}
        for raw_key, raw_updated in value.items():
            key = str(raw_key).strip()
            if not key:
                continue
            if isinstance(raw_updated, datetime):
                normalized[key] = raw_updated
            else:
                normalized[key] = _coerce_runtime_updated_at(raw_updated)
        return normalized
    return {str(key).strip(): None for key in value if str(key).strip()}


def _heartbeat_age_seconds(
    *,
    now: datetime,
    last_seen_at: datetime | None,
) -> int | None:
    if last_seen_at is None:
        return None
    delta = now - last_seen_at
    return max(int(delta.total_seconds()), 0)


def _is_stale(*, heartbeat_age_seconds: int | None, stale_after_seconds: int) -> bool:
    if heartbeat_age_seconds is None:
        return True
    return heartbeat_age_seconds > stale_after_seconds


def _runtime_activity_is_recent(
    *,
    now: datetime,
    runtime_updated_at: datetime | None,
    stale_after_seconds: int,
) -> bool:
    if runtime_updated_at is None:
        return False
    runtime_age_seconds = max(int((now - runtime_updated_at).total_seconds()), 0)
    return runtime_age_seconds <= stale_after_seconds


def continuity_requires_recovery(continuity: ContinuityState) -> bool:
    """Return true when continuity status should trigger automated recovery logic."""
    return continuity in RECOVERY_CONTINUITIES


class AgentContinuityService(OpenClawDBService):
    """Compute continuity status for all agents assigned to a board."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        runtime_session_keys_fetcher: RuntimeSessionSnapshotFetcher | None = None,
    ) -> None:
        super().__init__(session)
        self._runtime_session_keys_fetcher = runtime_session_keys_fetcher

    async def fetch_runtime_sessions(self, gateway: Gateway) -> RuntimeSessionSnapshot:
        """Fetch runtime sessions keyed by session key with optional update timestamps."""
        if self._runtime_session_keys_fetcher is not None:
            return _normalize_runtime_sessions(await self._runtime_session_keys_fetcher(gateway))
        payload = await openclaw_call("sessions.list", config=gateway_client_config(gateway))
        return _extract_runtime_sessions(payload)

    async def fetch_runtime_session_keys(self, gateway: Gateway) -> set[str]:
        """Fetch currently reachable session keys from the gateway runtime."""
        return set((await self.fetch_runtime_sessions(gateway)).keys())

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

        runtime_sessions: RuntimeSessionSnapshot = {}
        runtime_error: str | None = None
        gateway = await self._board_gateway(board=board)
        if gateway is None:
            runtime_error = "Board gateway is not configured."
        else:
            try:
                runtime_sessions = await self.fetch_runtime_sessions(gateway)
            except (HTTPException, OpenClawGatewayError, OSError, RuntimeError, ValueError) as exc:
                runtime_error = str(exc)

        now = utcnow()
        counts = {"alive": 0, "stale": 0, "unreachable": 0}
        continuity_items: list[AgentContinuityItem] = []

        for agent in agents:
            session_id = (agent.openclaw_session_id or "").strip() or None
            heartbeat_age = _heartbeat_age_seconds(now=now, last_seen_at=agent.last_seen_at)
            stale_after_seconds = int(
                stale_after_for_heartbeat_config(agent.heartbeat_config).total_seconds(),
            )
            stale = _is_stale(
                heartbeat_age_seconds=heartbeat_age,
                stale_after_seconds=stale_after_seconds,
            )

            runtime_reachable = True
            continuity_reason = "healthy"
            runtime_session_updated_at: datetime | None = None
            if runtime_error:
                runtime_reachable = False
                continuity_reason = "runtime_unavailable"
            elif session_id is None:
                runtime_reachable = False
                continuity_reason = "runtime_session_missing"
            elif session_id not in runtime_sessions:
                runtime_reachable = False
                continuity_reason = "runtime_session_unreachable"
            else:
                runtime_session_updated_at = runtime_sessions.get(session_id)
            if runtime_reachable and stale and _runtime_activity_is_recent(
                now=now,
                runtime_updated_at=runtime_session_updated_at,
                stale_after_seconds=stale_after_seconds,
            ):
                stale = False
                continuity_reason = "runtime_activity_recent"
            elif runtime_reachable and stale:
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
