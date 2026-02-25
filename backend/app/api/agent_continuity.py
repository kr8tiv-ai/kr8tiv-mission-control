"""Board-scoped agent continuity snapshot API."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import SQLModel

from app.api.deps import get_board_for_actor_read
from app.db.session import get_session
from app.models.boards import Board
from app.services.agent_continuity import AgentContinuityService

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/boards", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
BOARD_DEP = Depends(get_board_for_actor_read)


class AgentContinuityItemRead(SQLModel):
    """Serialized per-agent continuity details."""

    agent_id: UUID
    agent_name: str
    board_id: UUID | None
    status: str
    continuity: Literal["alive", "stale", "unreachable"]
    continuity_reason: str
    runtime_session_id: str | None
    runtime_reachable: bool
    last_seen_at: datetime | None
    heartbeat_age_seconds: int | None


class AgentContinuitySnapshotRead(SQLModel):
    """Board-level continuity probe payload."""

    board_id: UUID
    generated_at: datetime
    runtime_error: str | None = None
    counts: dict[str, int]
    agents: list[AgentContinuityItemRead]


@router.get("/{board_id}/agent-continuity", response_model=AgentContinuitySnapshotRead)
async def board_agent_continuity(
    board: Board = BOARD_DEP,
    session: AsyncSession = SESSION_DEP,
) -> AgentContinuitySnapshotRead:
    """Return a board continuity snapshot for automation and operator checks."""
    report = await AgentContinuityService(session).snapshot_for_board(board_id=board.id)
    return AgentContinuitySnapshotRead(
        board_id=report.board_id,
        generated_at=report.generated_at,
        runtime_error=report.runtime_error,
        counts=report.counts,
        agents=[
            AgentContinuityItemRead(
                agent_id=item.agent_id,
                agent_name=item.agent_name,
                board_id=item.board_id,
                status=item.status,
                continuity=item.continuity,
                continuity_reason=item.continuity_reason,
                runtime_session_id=item.runtime_session_id,
                runtime_reachable=item.runtime_reachable,
                last_seen_at=item.last_seen_at,
                heartbeat_age_seconds=item.heartbeat_age_seconds,
            )
            for item in report.agents
        ],
    )

