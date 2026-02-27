"""API routes for GSD run stage telemetry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeGuard
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.boards import Board
from app.models.gsd_runs import GSDRun
from app.schemas.gsd_runs import (
    GSDRunCreate,
    GSDRunRead,
    GSDRunSummaryRead,
    GSDRunUpdate,
    OwnerApprovalStatus,
)
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/gsd-runs", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)
BOARD_ID_QUERY = Query(default=None)
STAGE_QUERY = Query(default=None)
STATUS_QUERY = Query(default=None)


def _resolve_owner_approval_status(
    *,
    owner_approval_required: bool,
    requested_status: OwnerApprovalStatus | None,
    current_status: OwnerApprovalStatus | None = None,
) -> OwnerApprovalStatus:
    if not owner_approval_required:
        return "not_required"
    if requested_status is not None and requested_status != "not_required":
        return requested_status
    if current_status in {"pending", "approved", "rejected"}:
        return current_status
    return "pending"


def _as_read(row: GSDRun) -> GSDRunRead:
    return GSDRunRead(
        id=row.id,
        organization_id=row.organization_id,
        board_id=row.board_id,
        task_id=row.task_id,
        created_by_user_id=row.created_by_user_id,
        run_name=row.run_name,
        iteration_number=row.iteration_number,
        stage=row.stage,
        status=row.status,
        owner_approval_required=row.owner_approval_required,
        owner_approval_status=row.owner_approval_status,
        owner_approval_note=row.owner_approval_note,
        owner_approved_at=row.owner_approved_at,
        rollout_evidence_links=list(row.rollout_evidence_links),
        metrics_snapshot=dict(row.metrics_snapshot),
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _is_numeric_metric(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _compute_metric_deltas(
    *,
    current: Mapping[str, object],
    previous: Mapping[str, object],
) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for key, current_value in current.items():
        previous_value = previous.get(key)
        if not _is_numeric_metric(current_value) or not _is_numeric_metric(previous_value):
            continue
        deltas[key] = float(current_value) - float(previous_value)
    return deltas


async def _require_row(
    *,
    run_id: UUID,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> GSDRun:
    row = await GSDRun.objects.by_id(run_id).first(session)
    if row is None or row.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return row


async def _validate_board_scope(
    *,
    board_id: UUID | None,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> None:
    if board_id is None:
        return
    board = await Board.objects.by_id(board_id).first(session)
    if board is None or board.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")


async def _find_previous_iteration_row(
    *,
    current_row: GSDRun,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> GSDRun | None:
    statement = (
        select(GSDRun)
        .where(col(GSDRun.organization_id) == ctx.organization.id)
        .where(col(GSDRun.run_name) == current_row.run_name)
        .where(col(GSDRun.iteration_number) < current_row.iteration_number)
        .order_by(col(GSDRun.iteration_number).desc(), col(GSDRun.created_at).desc())
        .limit(1)
    )
    if current_row.board_id is None:
        statement = statement.where(col(GSDRun.board_id).is_(None))
    else:
        statement = statement.where(col(GSDRun.board_id) == current_row.board_id)
    return (await session.exec(statement)).first()


@router.get("", response_model=list[GSDRunRead])
async def list_gsd_runs(
    board_id: UUID | None = BOARD_ID_QUERY,
    stage: str | None = STAGE_QUERY,
    status_filter: str | None = STATUS_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> list[GSDRunRead]:
    """List GSD run telemetry records for the active organization."""
    await _validate_board_scope(board_id=board_id, session=session, ctx=ctx)
    statement = (
        select(GSDRun)
        .where(col(GSDRun.organization_id) == ctx.organization.id)
        .order_by(col(GSDRun.created_at).desc())
    )
    if board_id is not None:
        statement = statement.where(col(GSDRun.board_id) == board_id)
    if stage:
        statement = statement.where(col(GSDRun.stage) == stage.strip().lower())
    if status_filter:
        statement = statement.where(col(GSDRun.status) == status_filter.strip().lower())
    rows = (await session.exec(statement)).all()
    return [_as_read(row) for row in rows]


@router.post("", response_model=GSDRunRead)
async def create_gsd_run(
    payload: GSDRunCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> GSDRunRead:
    """Create a new GSD run telemetry record."""
    await _validate_board_scope(board_id=payload.board_id, session=session, ctx=ctx)
    now = utcnow()
    approval_status = _resolve_owner_approval_status(
        owner_approval_required=payload.owner_approval_required,
        requested_status=payload.owner_approval_status,
    )
    row = GSDRun(
        organization_id=ctx.organization.id,
        board_id=payload.board_id,
        task_id=payload.task_id,
        created_by_user_id=ctx.member.user_id,
        run_name=payload.run_name or "",
        iteration_number=payload.iteration_number,
        stage=payload.stage,
        status=payload.status,
        owner_approval_required=payload.owner_approval_required,
        owner_approval_status=approval_status,
        owner_approval_note=payload.owner_approval_note,
        owner_approved_at=(now if approval_status == "approved" else None),
        rollout_evidence_links=list(payload.rollout_evidence_links),
        metrics_snapshot=dict(payload.metrics_snapshot),
        completed_at=(now if payload.status == "completed" else None),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _as_read(row)


@router.get("/{run_id}", response_model=GSDRunRead)
async def get_gsd_run(
    run_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> GSDRunRead:
    """Fetch a single GSD run telemetry record by id."""
    row = await _require_row(run_id=run_id, session=session, ctx=ctx)
    return _as_read(row)


@router.get("/{run_id}/summary", response_model=GSDRunSummaryRead)
async def get_gsd_run_summary(
    run_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> GSDRunSummaryRead:
    """Fetch run details and previous-iteration metric deltas for the same run name."""
    row = await _require_row(run_id=run_id, session=session, ctx=ctx)
    previous_row = await _find_previous_iteration_row(current_row=row, session=session, ctx=ctx)
    run_read = _as_read(row)
    previous_read = _as_read(previous_row) if previous_row is not None else None
    deltas = _compute_metric_deltas(
        current=run_read.metrics_snapshot,
        previous=(previous_read.metrics_snapshot if previous_read is not None else {}),
    )
    return GSDRunSummaryRead(run=run_read, previous=previous_read, deltas=deltas)


@router.patch("/{run_id}", response_model=GSDRunRead)
async def update_gsd_run(
    run_id: UUID,
    payload: GSDRunUpdate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> GSDRunRead:
    """Patch stage progress, owner approvals, and rollout evidence for a run."""
    row = await _require_row(run_id=run_id, session=session, ctx=ctx)
    now = utcnow()

    if payload.stage is not None:
        row.stage = payload.stage
    if payload.status is not None:
        row.status = payload.status
        row.completed_at = now if payload.status == "completed" else None
    if payload.run_name is not None:
        row.run_name = payload.run_name
    if payload.iteration_number is not None:
        row.iteration_number = payload.iteration_number

    owner_approval_required = (
        payload.owner_approval_required
        if payload.owner_approval_required is not None
        else row.owner_approval_required
    )
    owner_approval_status = _resolve_owner_approval_status(
        owner_approval_required=owner_approval_required,
        requested_status=payload.owner_approval_status,
        current_status=row.owner_approval_status,  # type: ignore[arg-type]
    )
    row.owner_approval_required = owner_approval_required
    row.owner_approval_status = owner_approval_status
    row.owner_approved_at = now if owner_approval_status == "approved" else None
    if payload.owner_approval_note is not None:
        row.owner_approval_note = payload.owner_approval_note

    if payload.rollout_evidence_links is not None:
        row.rollout_evidence_links = list(payload.rollout_evidence_links)
    if payload.metrics_snapshot is not None:
        row.metrics_snapshot = dict(payload.metrics_snapshot)

    row.updated_at = now
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _as_read(row)
