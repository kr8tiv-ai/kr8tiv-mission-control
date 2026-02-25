"""Schemas for persona preset catalog CRUD and apply actions."""

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


def _normalize_identity_profile(profile: object) -> dict[str, str] | None:
    if profile is None:
        return None
    if not isinstance(profile, dict):
        return None
    normalized: dict[str, str] = {}
    for raw_key, raw_value in profile.items():
        key = str(raw_key).strip()
        if not key:
            continue
        value = str(raw_value).strip()
        if value:
            normalized[key] = value
    return normalized or None


class PersonaPresetCreate(SQLModel):
    """Payload for creating a persona preset in the active organization."""

    key: NonEmptyStr
    name: NonEmptyStr
    description: str | None = None
    deployment_mode: str = "team"
    identity_profile: dict[str, Any] | None = None
    identity_template: str | None = None
    soul_template: str | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", "identity_template", "soul_template", mode="before")
    @classmethod
    def normalize_optional_text_fields(cls, value: object) -> object | None:
        return _normalize_optional_text(value)

    @field_validator("identity_profile", mode="before")
    @classmethod
    def normalize_identity_profile(cls, value: object) -> dict[str, str] | None:
        return _normalize_identity_profile(value)

    @field_validator("deployment_mode", mode="before")
    @classmethod
    def normalize_deployment_mode(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        return text or "team"


class PersonaPresetRead(SQLModel):
    """Read model for persona preset resources."""

    id: UUID
    organization_id: UUID
    key: str
    name: str
    description: str | None = None
    deployment_mode: str
    identity_profile: dict[str, Any] | None = None
    identity_template: str | None = None
    soul_template: str | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PersonaPresetApplyRequest(SQLModel):
    """Request payload for applying a preset to an agent."""

    preset_id: UUID


class PersonaPresetApplyResponse(SQLModel):
    """Response emitted after applying a preset to an agent."""

    ok: bool = True
    agent_id: UUID
    preset_id: UUID
