"""Change request workflow API for customer-submitted modifications."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.change_requests import ChangeRequest
from app.schemas.change_requests import ChangeRequestCreate, ChangeRequestRead, ChangeRequestUpdate
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/change-requests", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"triage", "approved", "rejected"},
    "triage": {"approved", "rejected"},
    "approved": {"applied", "rejected"},
    "rejected": set(),
    "applied": set(),
}


def _as_read(row: ChangeRequest) -> ChangeRequestRead:
    return ChangeRequestRead(
        id=row.id,
        organization_id=row.organization_id,
        requested_by_user_id=row.requested_by_user_id,
        requested_for_agent_id=row.requested_for_agent_id,
        title=row.title,
        description=row.description,
        category=row.category,
        priority=row.priority,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        resolution_note=row.resolution_note,
        reviewed_by_user_id=row.reviewed_by_user_id,
        reviewed_at=row.reviewed_at,
        applied_at=row.applied_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _require_change_request(
    *,
    request_id: UUID,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> ChangeRequest:
    row = await ChangeRequest.objects.by_id(request_id).first(session)
    if row is None or row.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return row


@router.get("", response_model=list[ChangeRequestRead])
async def list_change_requests(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> list[ChangeRequestRead]:
    """List organization change requests ordered by newest first."""
    statement = (
        select(ChangeRequest)
        .where(col(ChangeRequest.organization_id) == ctx.organization.id)
        .order_by(col(ChangeRequest.created_at).desc())
    )
    rows = (await session.exec(statement)).all()
    return [_as_read(row) for row in rows]


@router.post("", response_model=ChangeRequestRead)
async def create_change_request(
    payload: ChangeRequestCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> ChangeRequestRead:
    """Submit a new change request."""
    now = utcnow()
    row = ChangeRequest(
        organization_id=ctx.organization.id,
        requested_by_user_id=ctx.member.user_id,
        requested_for_agent_id=payload.requested_for_agent_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        status="submitted",
        resolution_note=None,
        reviewed_by_user_id=None,
        reviewed_at=None,
        applied_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _as_read(row)


@router.get("/{request_id}", response_model=ChangeRequestRead)
async def get_change_request(
    request_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> ChangeRequestRead:
    """Fetch a single change request by id."""
    row = await _require_change_request(request_id=request_id, session=session, ctx=ctx)
    return _as_read(row)


@router.patch("/{request_id}", response_model=ChangeRequestRead)
async def update_change_request(
    request_id: UUID,
    payload: ChangeRequestUpdate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> ChangeRequestRead:
    """Update change request lifecycle state."""
    row = await _require_change_request(request_id=request_id, session=session, ctx=ctx)
    if payload.status != row.status:
        allowed = ALLOWED_TRANSITIONS.get(row.status, set())
        if payload.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot transition change request from '{row.status}' to '{payload.status}'.",
            )
        row.status = payload.status

    row.resolution_note = payload.resolution_note
    now = utcnow()
    row.updated_at = now
    if payload.status in {"triage", "approved", "rejected"}:
        row.reviewed_by_user_id = ctx.member.user_id
        row.reviewed_at = now
    if payload.status == "applied":
        row.applied_at = now
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _as_read(row)
