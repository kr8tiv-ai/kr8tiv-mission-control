"""Runtime NotebookLM capability-gate endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.db.session import get_session
from app.models.boards import Board
from app.models.tasks import Task
from app.schemas.notebook_ops import NotebookCapabilityGateRead, NotebookCapabilityGateSummaryRead
from app.services.notebooklm_capability_gate import evaluate_notebooklm_capability
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/runtime/notebook", tags=["control-plane"])
ORG_ADMIN_DEP = Depends(require_org_admin)
SESSION_DEP = Depends(get_session)
NOTEBOOK_ENABLED_MODES = ("notebook", "arena_notebook", "notebook_creation")
_SUMMARY_STATE_KEYS = ("ready", "retryable", "misconfig", "hard_fail", "unknown")


@router.get("/gate", response_model=NotebookCapabilityGateRead)
async def get_notebook_capability_gate(
    profile: str = Query(default="auto"),
    notebook_id: str | None = Query(default=None),
    require_notebook: bool = Query(default=False),
    _ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> NotebookCapabilityGateRead:
    """Return current NotebookLM capability gate status for requested query context."""
    result = await evaluate_notebooklm_capability(
        profile=profile,
        notebook_id=notebook_id,
        require_notebook=require_notebook,
    )
    return NotebookCapabilityGateRead(
        state=result.state,
        reason=result.reason,
        operator_message=result.operator_message,
        checked_at=result.checked_at,
        selected_profile=result.selected_profile,
        notebook_count=result.notebook_count,
    )


@router.get("/gate-summary", response_model=NotebookCapabilityGateSummaryRead)
async def get_notebook_capability_gate_summary(
    board_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> NotebookCapabilityGateSummaryRead:
    """Return board-scoped counts for notebook capability-gate states."""
    board = await Board.objects.by_id(board_id).first(session)
    if board is None or board.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    rows = (
        await session.exec(
            select(col(Task.notebook_gate_state))
            .where(col(Task.board_id) == board_id)
            .where(col(Task.task_mode).in_(NOTEBOOK_ENABLED_MODES))
        )
    ).all()

    counts = {key: 0 for key in _SUMMARY_STATE_KEYS}
    for state in rows:
        normalized = str(state or "").strip().lower()
        if normalized in counts and normalized != "unknown":
            counts[normalized] += 1
        else:
            counts["unknown"] += 1

    return NotebookCapabilityGateSummaryRead(
        board_id=board_id,
        total_notebook_tasks=len(rows),
        gate_counts=counts,
    )
