"""Schemas for runtime recovery policy and incident operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel


class RecoveryPolicyRead(SQLModel):
    """Read model for organization-scoped recovery policy settings."""

    id: UUID
    organization_id: UUID
    enabled: bool
    stale_after_seconds: int
    max_restarts_per_hour: int
    cooldown_seconds: int
    alert_dedupe_seconds: int
    alert_telegram: bool
    alert_whatsapp: bool
    alert_ui: bool
    created_at: datetime
    updated_at: datetime


class RecoveryPolicyUpdate(SQLModel):
    """Patch payload for organization-scoped recovery policy settings."""

    enabled: bool | None = None
    stale_after_seconds: int | None = None
    max_restarts_per_hour: int | None = None
    cooldown_seconds: int | None = None
    alert_dedupe_seconds: int | None = None
    alert_telegram: bool | None = None
    alert_whatsapp: bool | None = None
    alert_ui: bool | None = None


class RecoveryIncidentRead(SQLModel):
    """Read model for persisted recovery incident rows."""

    id: UUID
    organization_id: UUID
    board_id: UUID | None = None
    agent_id: UUID | None = None
    status: str
    reason: str
    action: str | None = None
    attempts: int
    last_error: str | None = None
    detected_at: datetime
    recovered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RecoveryRunRead(SQLModel):
    """Summary payload emitted by manual recovery run endpoint."""

    board_id: UUID
    generated_at: datetime
    total_incidents: int
    recovered: int
    failed: int
    suppressed: int
    incidents: list[RecoveryIncidentRead]
