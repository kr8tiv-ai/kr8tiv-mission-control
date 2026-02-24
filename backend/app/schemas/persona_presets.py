"""Schemas for persona preset CRUD and apply workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import field_validator
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


class PersonaPresetCreate(SQLModel):
    """Payload for creating an organization-scoped persona preset."""

    name: NonEmptyStr
    description: str | None = None
    preset_mode: NonEmptyStr = "team"
    identity_profile: dict[str, Any] | None = None
    identity_template: str | None = None
    soul_template: str | None = None

    @field_validator("description", "identity_template", "soul_template", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object | None:
        return _normalize_optional_text(value)


class PersonaPresetRead(SQLModel):
    """Persona preset read model."""

    id: UUID
    organization_id: UUID
    name: str
    description: str | None = None
    preset_mode: str
    identity_profile: dict[str, Any] | None = None
    identity_template: str | None = None
    soul_template: str | None = None
    created_at: datetime
    updated_at: datetime


class PersonaPresetApplyRequest(SQLModel):
    """Request payload for applying a preset to a specific agent."""

    preset_id: UUID


class PersonaPresetApplyResponse(SQLModel):
    """Result payload for preset apply operations."""

    applied: bool = True
    agent_id: UUID
    preset_id: UUID
