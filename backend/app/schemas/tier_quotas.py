"""Schemas for tier quota configuration and reads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel

from app.schemas.common import NonEmptyStr

_RUNTIME_TYPE_REFERENCES = (datetime, UUID, NonEmptyStr)


class TierQuotaUpsert(SQLModel):
    """Create or update an organization's tier quota policy."""

    tier_name: NonEmptyStr
    max_abilities: int = Field(ge=0)
    max_storage_mb: int = Field(ge=0)


class TierQuotaRead(SQLModel):
    """Read model for current tier quota policy."""

    id: UUID
    organization_id: UUID
    tier_name: str
    max_abilities: int
    max_storage_mb: int
    created_at: datetime
    updated_at: datetime
