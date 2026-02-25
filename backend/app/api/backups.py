"""Customer-owned backup reminder and confirmation API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.backups import BackupPolicy
from app.schemas.backups import (
    BackupConfirmationCreate,
    BackupConfirmationRead,
    BackupReminderRead,
)
from app.services.backups.reminder_service import REMINDER_INTERVAL, evaluate_reminder
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/backups", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)
DESTINATIONS = ["local_drive", "external_drive", "customer_cloud", "manual_export"]


def _as_confirmation_read(policy: BackupPolicy) -> BackupConfirmationRead:
    return BackupConfirmationRead(
        id=policy.id,
        organization_id=policy.organization_id,
        owner_user_id=policy.owner_user_id,
        status=policy.status,
        destination_type=policy.destination_type,  # type: ignore[arg-type]
        destination_label=policy.destination_label,
        last_confirmed_at=policy.last_confirmed_at,
        next_prompt_at=policy.next_prompt_at,
        stores_customer_payload=False,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


async def _get_or_create_policy(
    *,
    session: AsyncSession,
    ctx: OrganizationContext,
) -> BackupPolicy:
    policy = await BackupPolicy.objects.filter_by(organization_id=ctx.organization.id).first(session)
    if policy is not None:
        return policy

    now = utcnow()
    policy = BackupPolicy(
        organization_id=ctx.organization.id,
        owner_user_id=ctx.member.user_id,
        status="unconfirmed",
        warning_shown_at=None,
        last_prompted_at=None,
        next_prompt_at=None,
        last_confirmed_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy


@router.get("/reminder", response_model=BackupReminderRead)
async def get_backup_reminder(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> BackupReminderRead:
    """Return reminder status and warning for customer-owned backups."""
    policy = await _get_or_create_policy(session=session, ctx=ctx)
    now = utcnow()
    reminder = evaluate_reminder(
        status=policy.status,
        next_prompt_at=policy.next_prompt_at,
        now=now,
    )
    if reminder.reminder_due:
        policy.warning_shown_at = now
        policy.last_prompted_at = now
    policy.next_prompt_at = reminder.next_prompt_at
    policy.updated_at = now
    session.add(policy)
    await session.commit()
    await session.refresh(policy)

    return BackupReminderRead(
        organization_id=policy.organization_id,
        status=policy.status,
        reminder_due=reminder.reminder_due,
        cadence_per_week=reminder.cadence_per_week,
        warning=reminder.warning,
        recommended_destinations=DESTINATIONS,  # type: ignore[arg-type]
        next_prompt_at=policy.next_prompt_at,
    )


@router.post("/confirm", response_model=BackupConfirmationRead)
async def confirm_backup_policy(
    payload: BackupConfirmationCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> BackupConfirmationRead:
    """Persist owner confirmation metadata for backup destination and cadence."""
    if payload.wants_backup and payload.destination_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="destination_type is required when wants_backup is true.",
        )

    policy = await _get_or_create_policy(session=session, ctx=ctx)
    now = utcnow()
    policy.owner_user_id = ctx.member.user_id
    policy.destination_type = payload.destination_type
    policy.destination_label = payload.destination_label
    policy.status = "confirmed" if payload.wants_backup else "declined"
    policy.last_confirmed_at = now if payload.wants_backup else None
    policy.warning_shown_at = now if not payload.wants_backup else policy.warning_shown_at
    policy.next_prompt_at = now + REMINDER_INTERVAL
    policy.updated_at = now
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return _as_confirmation_read(policy)
