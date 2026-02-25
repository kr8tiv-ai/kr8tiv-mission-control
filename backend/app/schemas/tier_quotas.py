"""Schemas for tier quota policy API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.schemas.common import NonEmptyStr

_RUNTIME_TYPE_REFERENCES = (datetime, UUID, NonEmptyStr)


class TierQuotaUpsert(SQLModel):
    """Payload for creating or updating a tier quota policy."""

    max_abilities: int = Field(ge=1)
    max_storage_mb: int = Field(ge=1)


class TierQuotaRead(SQLModel):
    """Read model for tier quota policies."""

    id: UUID
    organization_id: UUID
    tier: str
    max_abilities: int
    max_storage_mb: int
    created_at: datetime
    updated_at: datetime


class TierQuotaScope(SQLModel):
    """Optional tier selector used by other policy APIs."""

    tier: str = "personal"

    @field_validator("tier", mode="before")
    @classmethod
    def normalize_tier(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        return text or "personal"
