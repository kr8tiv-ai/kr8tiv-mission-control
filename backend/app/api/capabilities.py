"""Capabilities catalog APIs for skills, libraries, and devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.capabilities import Capability
from app.schemas.capabilities import CapabilityCreate, CapabilityKind, CapabilityRead
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/capabilities", tags=["capabilities"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


def _to_capability_read(capability: Capability) -> CapabilityRead:
    return CapabilityRead(
        id=capability.id,
        organization_id=capability.organization_id,
        kind=capability.kind,  # type: ignore[arg-type]
        name=capability.name,
        description=capability.description,
        risk_level=capability.risk_level,  # type: ignore[arg-type]
        scope=capability.scope,  # type: ignore[arg-type]
        metadata=dict(capability.metadata_ or {}),
        created_at=capability.created_at,
        updated_at=capability.updated_at,
    )


@router.post(
    "",
    response_model=CapabilityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_capability(
    payload: CapabilityCreate,
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> CapabilityRead:
    existing = (
        await session.exec(
            select(Capability).where(
                col(Capability.organization_id) == org_ctx.organization.id,
                col(Capability.kind) == payload.kind,
                col(Capability.name) == payload.name,
            ),
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Capability already exists for this organization",
        )

    capability = Capability(
        organization_id=org_ctx.organization.id,
        kind=payload.kind,
        name=payload.name,
        description=payload.description,
        risk_level=payload.risk_level,
        scope=payload.scope,
        metadata_=payload.metadata_,
    )
    session.add(capability)
    await session.commit()
    await session.refresh(capability)
    return _to_capability_read(capability)


@router.get(
    "",
    response_model=list[CapabilityRead],
)
async def list_capabilities(
    kind: CapabilityKind | None = Query(default=None),
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> list[CapabilityRead]:
    statement = select(Capability).where(col(Capability.organization_id) == org_ctx.organization.id)
    if kind is not None:
        statement = statement.where(col(Capability.kind) == kind)
    statement = statement.order_by(Capability.created_at, Capability.name)
    rows = (await session.exec(statement)).all()
    return [_to_capability_read(row) for row in rows]
