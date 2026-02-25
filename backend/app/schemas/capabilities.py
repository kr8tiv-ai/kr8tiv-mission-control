"""Schemas for capability catalog API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator
from sqlmodel import SQLModel

from app.schemas.common import NonEmptyStr

_RUNTIME_TYPE_REFERENCES = (datetime, UUID, NonEmptyStr)

CapabilityType = Literal["skill", "library", "device"]


def _normalize_optional_text(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value


class CapabilityCreate(SQLModel):
    """Payload for creating a capability catalog entry."""

    capability_type: CapabilityType
    key: NonEmptyStr
    name: NonEmptyStr
    description: str | None = None
    version: str | None = None
    risk_level: str = "low"
    access_scope: str = "tenant"
    enabled: bool = True
    metadata_: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", "version", "risk_level", "access_scope", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: object) -> object | None:
        return _normalize_optional_text(value)


class CapabilityRead(SQLModel):
    """Read model for capability catalog entries."""

    id: UUID
    organization_id: UUID
    capability_type: CapabilityType
    key: str
    name: str
    description: str | None = None
    version: str | None = None
    risk_level: str
    access_scope: str
    enabled: bool
    metadata_: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
