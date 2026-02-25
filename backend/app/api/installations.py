"""Installation governance API with ask-first and break-glass controls."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.installations import InstallationRequest
from app.models.override_sessions import OverrideSession
from app.models.tier_quotas import TierQuota
from app.schemas.installations import (
    InstallationRequestCreate,
    InstallationRequestRead,
    InstallationRequestResolve,
    OverrideSessionRead,
    OverrideSessionStart,
)
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/installations", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


def _normalize_tier(value: object) -> str:
    if isinstance(value, str):
        text = value.strip().lower()
        return text or "personal"
    return "personal"


def _coerce_storage_mb(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        try:
            parsed = float(text)
        except ValueError:
            return 0
        return max(int(parsed), 0)
    return 0


async def _ensure_quota_available(
    *,
    payload: InstallationRequestCreate,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> None:
    requested_tier = _normalize_tier(payload.requested_payload.get("tier"))
    quota = await TierQuota.objects.filter_by(
        organization_id=ctx.organization.id,
        tier=requested_tier,
    ).first(session)
    if quota is None:
        return

    approved_requests = (
        await InstallationRequest.objects.filter_by(
            organization_id=ctx.organization.id,
            status="approved",
        ).all(session)
    )
    if len(approved_requests) >= quota.max_abilities:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Install blocked: ability slots exhausted for "
                f"tier '{requested_tier}' ({quota.max_abilities} max)."
            ),
        )

    used_storage_mb = sum(
        _coerce_storage_mb((row.requested_payload or {}).get("estimated_storage_mb"))
        for row in approved_requests
    )
    requested_storage_mb = _coerce_storage_mb(payload.requested_payload.get("estimated_storage_mb"))
    if used_storage_mb + requested_storage_mb > quota.max_storage_mb:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Install blocked: storage quota exceeded for "
                f"tier '{requested_tier}' "
                f"({used_storage_mb + requested_storage_mb}MB requested, "
                f"{quota.max_storage_mb}MB max)."
            ),
        )


def _as_installation_read(row: InstallationRequest) -> InstallationRequestRead:
    return InstallationRequestRead(
        id=row.id,
        organization_id=row.organization_id,
        capability_id=row.capability_id,
        agent_id=row.agent_id,
        requested_by_user_id=row.requested_by_user_id,
        package_class=row.package_class,
        package_key=row.package_key,
        approval_mode=row.approval_mode,
        status=row.status,
        approved_by_user_id=row.approved_by_user_id,
        approved_at=row.approved_at,
        denied_reason=row.denied_reason,
        requested_payload=row.requested_payload or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _as_override_read(row: OverrideSession) -> OverrideSessionRead:
    return OverrideSessionRead(
        id=row.id,
        organization_id=row.organization_id,
        started_by_user_id=row.started_by_user_id,
        reason=row.reason,
        expires_at=row.expires_at,
        active=row.active,
        ended_at=row.ended_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/requests", response_model=InstallationRequestRead)
async def create_installation_request(
    payload: InstallationRequestCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> InstallationRequestRead:
    """Create an installation request governed by approval policy."""
    await _ensure_quota_available(payload=payload, session=session, ctx=ctx)

    now = utcnow()
    status_value = "pending_owner_approval" if payload.approval_mode == "ask_first" else "approved"
    request = InstallationRequest(
        organization_id=ctx.organization.id,
        capability_id=payload.capability_id,
        agent_id=payload.agent_id,
        requested_by_user_id=ctx.member.user_id,
        package_class=payload.package_class,
        package_key=payload.package_key,
        approval_mode=payload.approval_mode,
        status=status_value,
        approved_by_user_id=(ctx.member.user_id if status_value == "approved" else None),
        approved_at=(now if status_value == "approved" else None),
        requested_payload=dict(payload.requested_payload),
        created_at=now,
        updated_at=now,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return _as_installation_read(request)


@router.post("/requests/{request_id}/resolve", response_model=InstallationRequestRead)
async def resolve_installation_request(
    request_id: UUID,
    payload: InstallationRequestResolve,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> InstallationRequestRead:
    """Approve or reject an installation request."""
    request = await InstallationRequest.objects.by_id(request_id).first(session)
    if request is None or request.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if request.status != "pending_owner_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request is no longer pending approval.",
        )
    if payload.approved:
        request.status = "approved"
        request.approved_by_user_id = ctx.member.user_id
        request.approved_at = utcnow()
        request.denied_reason = None
    else:
        if not payload.reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Rejection reason is required.",
            )
        request.status = "rejected"
        request.denied_reason = payload.reason
        request.approved_by_user_id = None
        request.approved_at = None
    request.updated_at = utcnow()
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return _as_installation_read(request)


@router.post("/override/start", response_model=OverrideSessionRead)
async def start_override_session(
    payload: OverrideSessionStart,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> OverrideSessionRead:
    """Start a time-bound break-glass override session."""
    now = utcnow()
    override = OverrideSession(
        organization_id=ctx.organization.id,
        started_by_user_id=ctx.member.user_id,
        reason=payload.reason,
        expires_at=now + timedelta(minutes=payload.ttl_minutes),
        active=True,
        ended_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(override)
    await session.commit()
    await session.refresh(override)
    return _as_override_read(override)


@router.post("/override/{override_id}/end", response_model=OverrideSessionRead)
async def end_override_session(
    override_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> OverrideSessionRead:
    """End an active break-glass override session."""
    statement = select(OverrideSession).where(col(OverrideSession.id) == override_id)
    override = (await session.exec(statement)).first()
    if override is None or override.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    override.active = False
    override.ended_at = utcnow()
    override.updated_at = utcnow()
    session.add(override)
    await session.commit()
    await session.refresh(override)
    return _as_override_read(override)
