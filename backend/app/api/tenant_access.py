"""Tenant self-access endpoint for mission control context."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_org_member
from app.schemas.tenant_access import TenantMemberSummary, TenantOrganizationSummary, TenantSelfAccessRead
from app.services.organizations import OrganizationContext

router = APIRouter(prefix="/tenant", tags=["control-plane"])
ORG_MEMBER_DEP = Depends(require_org_member)


@router.get("/self", response_model=TenantSelfAccessRead)
async def tenant_self(
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> TenantSelfAccessRead:
    """Return caller's tenant-scoped mission-control access context."""
    return TenantSelfAccessRead(
        organization=TenantOrganizationSummary(
            id=ctx.organization.id,
            name=ctx.organization.name,
        ),
        member=TenantMemberSummary(
            id=ctx.member.id,
            user_id=ctx.member.user_id,
            role=ctx.member.role,
            all_boards_read=ctx.member.all_boards_read,
            all_boards_write=ctx.member.all_boards_write,
        ),
    )
