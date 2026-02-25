"""Capability catalog API for skills, libraries, and devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select

from app.api.deps import require_org_admin, require_org_member
from app.core.time import utcnow
from app.db.session import get_session
from app.models.capabilities import Capability
from app.schemas.capabilities import CapabilityCreate, CapabilityRead, CapabilityType
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/capabilities", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_MEMBER_DEP = Depends(require_org_member)
ORG_ADMIN_DEP = Depends(require_org_admin)


def _as_read(capability: Capability) -> CapabilityRead:
    return CapabilityRead(
        id=capability.id,
        organization_id=capability.organization_id,
        capability_type=capability.capability_type,  # type: ignore[arg-type]
        key=capability.key,
        name=capability.name,
        description=capability.description,
        version=capability.version,
        risk_level=capability.risk_level,
        access_scope=capability.access_scope,
        enabled=capability.enabled,
        metadata_=capability.metadata_ or {},
        created_at=capability.created_at,
        updated_at=capability.updated_at,
    )


@router.get("", response_model=list[CapabilityRead])
async def list_capabilities(
    capability_type: CapabilityType | None = Query(default=None),
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> list[CapabilityRead]:
    """List organization capability entries, optionally filtered by type."""
    statement = select(Capability).where(col(Capability.organization_id) == ctx.organization.id)
    if capability_type is not None:
        statement = statement.where(col(Capability.capability_type) == capability_type)
    statement = statement.order_by(col(Capability.created_at).asc())
    rows = (await session.exec(statement)).all()
    return [_as_read(row) for row in rows]


@router.post("", response_model=CapabilityRead)
async def create_capability(
    payload: CapabilityCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> CapabilityRead:
    """Create a capability entry for the active organization."""
    existing = await Capability.objects.filter_by(
        organization_id=ctx.organization.id,
        capability_type=payload.capability_type,
        key=payload.key,
    ).first(session)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Capability key already exists for this type.",
        )

    now = utcnow()
    capability = Capability(
        organization_id=ctx.organization.id,
        capability_type=payload.capability_type,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        risk_level=payload.risk_level,
        access_scope=payload.access_scope,
        enabled=payload.enabled,
        metadata_=dict(payload.metadata_),
        created_at=now,
        updated_at=now,
    )
    session.add(capability)
    await session.commit()
    await session.refresh(capability)
    return _as_read(capability)
