"""Runtime recovery policy, incident, and run endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.boards import Board
from app.models.recovery_incidents import RecoveryIncident
from app.models.recovery_policies import RecoveryPolicy
from app.schemas.recovery_ops import (
    RecoveryIncidentRead,
    RecoveryPolicyRead,
    RecoveryPolicyUpdate,
    RecoveryRunRead,
)
from app.services.organizations import OrganizationContext
from app.services.runtime.recovery_engine import RecoveryEngine
from app.services.runtime.gsd_metrics_sync import sync_recovery_summary_to_gsd_run

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/runtime/recovery", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)
BOARD_ID_QUERY = Query(default=None)
LIMIT_QUERY = Query(default=100, ge=1, le=500)


def _as_policy_read(row: RecoveryPolicy) -> RecoveryPolicyRead:
    return RecoveryPolicyRead(
        id=row.id,
        organization_id=row.organization_id,
        enabled=row.enabled,
        stale_after_seconds=row.stale_after_seconds,
        max_restarts_per_hour=row.max_restarts_per_hour,
        cooldown_seconds=row.cooldown_seconds,
        alert_dedupe_seconds=row.alert_dedupe_seconds,
        alert_telegram=row.alert_telegram,
        alert_whatsapp=row.alert_whatsapp,
        alert_ui=row.alert_ui,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _as_incident_read(row: RecoveryIncident) -> RecoveryIncidentRead:
    return RecoveryIncidentRead(
        id=row.id,
        organization_id=row.organization_id,
        board_id=row.board_id,
        agent_id=row.agent_id,
        status=row.status,
        reason=row.reason,
        action=row.action,
        attempts=row.attempts,
        last_error=row.last_error,
        detected_at=row.detected_at,
        recovered_at=row.recovered_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _ensure_policy(
    *,
    session: AsyncSession,
    organization_id: UUID,
) -> RecoveryPolicy:
    row = await RecoveryPolicy.objects.filter_by(organization_id=organization_id).first(session)
    if row is not None:
        return row
    row = RecoveryPolicy(organization_id=organization_id)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.get("/policy", response_model=RecoveryPolicyRead)
async def get_recovery_policy(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> RecoveryPolicyRead:
    """Return organization recovery policy defaults/settings."""
    row = await _ensure_policy(session=session, organization_id=ctx.organization.id)
    return _as_policy_read(row)


@router.put("/policy", response_model=RecoveryPolicyRead)
async def update_recovery_policy(
    payload: RecoveryPolicyUpdate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> RecoveryPolicyRead:
    """Update organization recovery policy settings."""
    row = await _ensure_policy(session=session, organization_id=ctx.organization.id)
    patch = payload.model_dump(exclude_unset=True)
    for key, value in patch.items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _as_policy_read(row)


@router.get("/incidents", response_model=list[RecoveryIncidentRead])
async def list_recovery_incidents(
    board_id: UUID | None = BOARD_ID_QUERY,
    limit: int = LIMIT_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> list[RecoveryIncidentRead]:
    """List recent recovery incidents for the organization, optionally board-scoped."""
    statement = (
        select(RecoveryIncident)
        .where(col(RecoveryIncident.organization_id) == ctx.organization.id)
        .order_by(col(RecoveryIncident.detected_at).desc())
        .limit(limit)
    )
    if board_id is not None:
        statement = statement.where(col(RecoveryIncident.board_id) == board_id)
    rows = (await session.exec(statement)).all()
    return [_as_incident_read(row) for row in rows]


@router.post("/run", response_model=RecoveryRunRead)
async def run_recovery_now(
    board_id: UUID,
    gsd_run_id: UUID | None = Query(
        default=None,
        description="Optional GSD run id to receive recovery summary metrics.",
    ),
    force: bool = Query(default=False, description="Bypass cooldown and force immediate heartbeat resync."),
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> RecoveryRunRead:
    """Execute a one-shot continuity recovery evaluation for the given board."""
    board = await Board.objects.by_id(board_id).first(session)
    if board is None or board.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    incidents = await RecoveryEngine(
        session=session,
        force_heartbeat_resync=force,
    ).evaluate_board(
        board_id=board.id,
        bypass_cooldown=force,
    )
    counts = {"recovered": 0, "failed": 0, "suppressed": 0}
    for incident in incidents:
        if incident.status in counts:
            counts[incident.status] += 1

    if gsd_run_id is not None:
        synced = await sync_recovery_summary_to_gsd_run(
            session=session,
            organization_id=ctx.organization.id,
            board_id=board.id,
            gsd_run_id=gsd_run_id,
            total_incidents=len(incidents),
            recovered=counts["recovered"],
            failed=counts["failed"],
            suppressed=counts["suppressed"],
        )
        if synced is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GSD run not found")

    return RecoveryRunRead(
        board_id=board.id,
        generated_at=utcnow(),
        total_incidents=len(incidents),
        recovered=counts["recovered"],
        failed=counts["failed"],
        suppressed=counts["suppressed"],
        incidents=[_as_incident_read(row) for row in incidents],
    )
