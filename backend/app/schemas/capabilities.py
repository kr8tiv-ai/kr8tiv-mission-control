"""Schemas for capabilities catalog CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator
from sqlmodel import SQLModel

from app.schemas.common import NonEmptyStr

_RUNTIME_TYPE_REFERENCES = (datetime, UUID, NonEmptyStr)

CapabilityKind = Literal["skill", "library", "device"]
CapabilityRiskLevel = Literal["low", "medium", "high", "critical"]
CapabilityScope = Literal["team", "individual", "global"]


def _normalize_optional_text(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value


class CapabilityCreate(SQLModel):
    """Payload for creating a capability catalog record."""

    kind: CapabilityKind
    name: NonEmptyStr
    description: str | None = None
    risk_level: CapabilityRiskLevel = "medium"
    scope: CapabilityScope = "team"
    metadata_: dict[str, object] = Field(
        default_factory=dict,
        alias="metadata",
        serialization_alias="metadata",
        validation_alias="metadata",
    )

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object | None:
        return _normalize_optional_text(value)


class CapabilityRead(SQLModel):
    """Capability catalog read model."""

    id: UUID
    organization_id: UUID
    kind: CapabilityKind
    name: str
    description: str | None = None
    risk_level: CapabilityRiskLevel
    scope: CapabilityScope
    metadata_: dict[str, object] = Field(
        alias="metadata",
        serialization_alias="metadata",
        validation_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime
