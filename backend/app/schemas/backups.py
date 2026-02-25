"""Schemas for customer-owned backup reminder and confirmation workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator
from sqlmodel import SQLModel

from app.schemas.common import NonEmptyStr

_RUNTIME_TYPE_REFERENCES = (datetime, UUID, NonEmptyStr)

BackupDestinationType = Literal[
    "local_drive",
    "external_drive",
    "customer_cloud",
    "manual_export",
]


def _normalize_optional_text(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value


class BackupReminderRead(SQLModel):
    """Backup reminder status payload surfaced to owner/admin callers."""

    organization_id: UUID
    status: str
    reminder_due: bool
    cadence_per_week: int = 2
    warning: str
    recommended_destinations: list[BackupDestinationType] = Field(default_factory=list)
    next_prompt_at: datetime | None = None


class BackupConfirmationCreate(SQLModel):
    """Payload for owner confirmation of local backup behavior."""

    wants_backup: bool = True
    destination_type: BackupDestinationType | None = None
    destination_label: str | None = None

    @field_validator("destination_label", mode="before")
    @classmethod
    def normalize_destination_label(cls, value: object) -> object | None:
        return _normalize_optional_text(value)


class BackupConfirmationRead(SQLModel):
    """Read model for persisted backup confirmation metadata."""

    id: UUID
    organization_id: UUID
    owner_user_id: UUID | None = None
    status: str
    destination_type: BackupDestinationType | None = None
    destination_label: str | None = None
    last_confirmed_at: datetime | None = None
    next_prompt_at: datetime | None = None
    stores_customer_payload: bool = False
    created_at: datetime
    updated_at: datetime
