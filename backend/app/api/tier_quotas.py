"""Tier quota API for ability/storage limits by deployment tier."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.tier_quotas import TierQuota
from app.schemas.tier_quotas import TierQuotaRead, TierQuotaUpsert
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/tier-quotas", tags=["tier-quotas"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


def _to_read(quota: TierQuota) -> TierQuotaRead:
    return TierQuotaRead(
        id=quota.id,
        organization_id=quota.organization_id,
        tier_name=quota.tier_name,
        max_abilities=quota.max_abilities,
        max_storage_mb=quota.max_storage_mb,
        created_at=quota.created_at,
        updated_at=quota.updated_at,
    )


@router.post(
    "",
    response_model=TierQuotaRead,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_tier_quota(
    payload: TierQuotaUpsert,
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> TierQuotaRead:
    now = utcnow()
    quota = (
        await session.exec(
            select(TierQuota).where(col(TierQuota.organization_id) == org_ctx.organization.id),
        )
    ).first()
    if quota is None:
        quota = TierQuota(
            organization_id=org_ctx.organization.id,
            tier_name=payload.tier_name,
            max_abilities=payload.max_abilities,
            max_storage_mb=payload.max_storage_mb,
        )
    else:
        quota.tier_name = payload.tier_name
        quota.max_abilities = payload.max_abilities
        quota.max_storage_mb = payload.max_storage_mb
        quota.updated_at = now

    session.add(quota)
    await session.commit()
    await session.refresh(quota)
    return _to_read(quota)


@router.get(
    "/current",
    response_model=TierQuotaRead | None,
)
async def get_current_tier_quota(
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> TierQuotaRead | None:
    quota = (
        await session.exec(
            select(TierQuota).where(col(TierQuota.organization_id) == org_ctx.organization.id),
        )
    ).first()
    if quota is None:
        return None
    return _to_read(quota)
