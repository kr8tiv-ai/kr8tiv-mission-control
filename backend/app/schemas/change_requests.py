"""Schemas for change request workflow APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import field_validator
from sqlmodel import SQLModel

from app.schemas.common import NonEmptyStr

_RUNTIME_TYPE_REFERENCES = (datetime, UUID, NonEmptyStr)

ChangeRequestPriority = Literal["low", "medium", "high", "urgent"]
ChangeRequestStatus = Literal["submitted", "triage", "approved", "rejected", "applied"]


def _normalize_optional_text(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value


class ChangeRequestCreate(SQLModel):
    """Payload for creating a customer change request."""

    title: NonEmptyStr
    description: NonEmptyStr
    category: NonEmptyStr = "general"
    priority: ChangeRequestPriority = "medium"
    requested_for_agent_id: UUID | None = None


class ChangeRequestUpdate(SQLModel):
    """Payload for updating lifecycle state of a change request."""

    status: ChangeRequestStatus
    resolution_note: str | None = None

    @field_validator("resolution_note", mode="before")
    @classmethod
    def normalize_resolution_note(cls, value: object) -> object | None:
        return _normalize_optional_text(value)


class ChangeRequestRead(SQLModel):
    """Read model for change request lifecycle records."""

    id: UUID
    organization_id: UUID
    requested_by_user_id: UUID | None = None
    requested_for_agent_id: UUID | None = None
    title: str
    description: str
    category: str
    priority: ChangeRequestPriority
    status: ChangeRequestStatus
    resolution_note: str | None = None
    reviewed_by_user_id: UUID | None = None
    reviewed_at: datetime | None = None
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
