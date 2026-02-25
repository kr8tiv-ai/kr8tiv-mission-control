"""Schemas for installation governance and break-glass override sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator
from sqlmodel import SQLModel

from app.schemas.common import NonEmptyStr

_RUNTIME_TYPE_REFERENCES = (datetime, UUID, NonEmptyStr)


def _normalize_optional_text(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value


class InstallationRequestCreate(SQLModel):
    """Payload for creating an installation request."""

    package_class: NonEmptyStr
    package_key: NonEmptyStr
    capability_id: UUID | None = None
    agent_id: UUID | None = None
    approval_mode: str = "ask_first"
    requested_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("approval_mode", mode="before")
    @classmethod
    def normalize_approval_mode(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        return text or "ask_first"


class InstallationRequestResolve(SQLModel):
    """Approval or rejection payload for installation requests."""

    approved: bool
    reason: str | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object | None:
        return _normalize_optional_text(value)


class InstallationRequestRead(SQLModel):
    """Read model for installation request records."""

    id: UUID
    organization_id: UUID
    capability_id: UUID | None = None
    agent_id: UUID | None = None
    requested_by_user_id: UUID | None = None
    package_class: str
    package_key: str
    approval_mode: str
    status: str
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    denied_reason: str | None = None
    requested_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class OverrideSessionStart(SQLModel):
    """Payload to start a break-glass override session."""

    reason: NonEmptyStr
    ttl_minutes: int = Field(default=30, ge=1, le=240)


class OverrideSessionRead(SQLModel):
    """Read model for break-glass override sessions."""

    id: UUID
    organization_id: UUID
    started_by_user_id: UUID | None = None
    reason: str
    expires_at: datetime
    active: bool
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
