"""Tier quota policy API for ability slot and storage limits."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlmodel import col, select

from app.api.deps import require_org_admin, require_org_member
from app.core.time import utcnow
from app.db.session import get_session
from app.models.tier_quotas import TierQuota
from app.schemas.tier_quotas import TierQuotaRead, TierQuotaUpsert
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/tier-quotas", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_MEMBER_DEP = Depends(require_org_member)
ORG_ADMIN_DEP = Depends(require_org_admin)


def _normalize_tier(value: str | None) -> str:
    return str(value or "personal").strip().lower() or "personal"


def _as_read(row: TierQuota) -> TierQuotaRead:
    return TierQuotaRead(
        id=row.id,
        organization_id=row.organization_id,
        tier=row.tier,
        max_abilities=row.max_abilities,
        max_storage_mb=row.max_storage_mb,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[TierQuotaRead])
async def list_tier_quotas(
    tier: str | None = Query(default=None),
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> list[TierQuotaRead]:
    """List tier quota policies for the organization."""
    statement = select(TierQuota).where(col(TierQuota.organization_id) == ctx.organization.id)
    if tier is not None:
        statement = statement.where(col(TierQuota.tier) == _normalize_tier(tier))
    statement = statement.order_by(col(TierQuota.tier).asc())
    rows = (await session.exec(statement)).all()
    return [_as_read(row) for row in rows]


@router.put("/{tier}", response_model=TierQuotaRead)
async def upsert_tier_quota(
    tier: str,
    payload: TierQuotaUpsert,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TierQuotaRead:
    """Create or update a tier quota policy."""
    normalized_tier = _normalize_tier(tier)
    now = utcnow()
    existing = await TierQuota.objects.filter_by(
        organization_id=ctx.organization.id,
        tier=normalized_tier,
    ).first(session)
    if existing is None:
        existing = TierQuota(
            organization_id=ctx.organization.id,
            tier=normalized_tier,
            max_abilities=payload.max_abilities,
            max_storage_mb=payload.max_storage_mb,
            created_at=now,
            updated_at=now,
        )
    else:
        existing.max_abilities = payload.max_abilities
        existing.max_storage_mb = payload.max_storage_mb
        existing.updated_at = now
    session.add(existing)
    await session.commit()
    await session.refresh(existing)
    return _as_read(existing)
