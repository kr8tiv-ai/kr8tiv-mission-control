"""Installation governance APIs with ask-first and break-glass controls."""

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
from app.schemas.installations import (
    InstallationExecuteRequest,
    InstallationExecuteResponse,
    InstallationRequestCreate,
    InstallationRequestRead,
    OverrideSessionCreate,
    OverrideSessionRead,
)
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/installations", tags=["installations"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


def _to_installation_read(request: InstallationRequest) -> InstallationRequestRead:
    return InstallationRequestRead(
        id=request.id,
        organization_id=request.organization_id,
        capability_id=request.capability_id,
        title=request.title,
        install_command=request.install_command,
        approval_mode=request.approval_mode,  # type: ignore[arg-type]
        status=request.status,  # type: ignore[arg-type]
        override_session_id=request.override_session_id,
        requested_payload=request.requested_payload,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def _to_override_read(session: OverrideSession) -> OverrideSessionRead:
    return OverrideSessionRead(
        id=session.id,
        organization_id=session.organization_id,
        reason=session.reason,
        expires_at=session.expires_at,
        active=session.active,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post(
    "/requests",
    response_model=InstallationRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_installation_request(
    payload: InstallationRequestCreate,
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> InstallationRequestRead:
    now = utcnow()
    request = InstallationRequest(
        organization_id=org_ctx.organization.id,
        capability_id=payload.capability_id,
        title=payload.title,
        install_command=payload.install_command,
        approval_mode=payload.approval_mode,
        status="approved" if payload.approval_mode == "auto" else "pending_owner_approval",
        requested_payload=payload.requested_payload,
        updated_at=now,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return _to_installation_read(request)


@router.post(
    "/override-sessions",
    response_model=OverrideSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_override_session(
    payload: OverrideSessionCreate,
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> OverrideSessionRead:
    now = utcnow()
    override = OverrideSession(
        organization_id=org_ctx.organization.id,
        reason=payload.reason,
        expires_at=now + timedelta(minutes=payload.ttl_minutes),
    )
    session.add(override)
    await session.commit()
    await session.refresh(override)
    return _to_override_read(override)


@router.post(
    "/requests/{request_id}/execute",
    response_model=InstallationExecuteResponse,
)
async def execute_installation_request(
    request_id: UUID,
    payload: InstallationExecuteRequest,
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> InstallationExecuteResponse:
    request = (
        await session.exec(
            select(InstallationRequest).where(
                col(InstallationRequest.id) == request_id,
                col(InstallationRequest.organization_id) == org_ctx.organization.id,
            ),
        )
    ).first()
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    now = utcnow()
    if request.status == "executed":
        return InstallationExecuteResponse(
            executed=True,
            request_id=request.id,
            status="executed",
        )

    if request.status != "approved":
        if payload.override_session_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Owner approval is required before execution",
            )
        override = (
            await session.exec(
                select(OverrideSession).where(
                    col(OverrideSession.id) == payload.override_session_id,
                    col(OverrideSession.organization_id) == org_ctx.organization.id,
                    col(OverrideSession.active).is_(True),
                ),
            )
        ).first()
        if override is None or override.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired override session",
            )
        request.override_session_id = override.id

    request.status = "executed"
    request.updated_at = now
    session.add(request)
    await session.commit()

    return InstallationExecuteResponse(
        executed=True,
        request_id=request.id,
        status="executed",
    )
