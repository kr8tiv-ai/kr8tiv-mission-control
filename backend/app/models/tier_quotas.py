"""Tier quota records controlling ability and storage limits per organization."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class TierQuota(QueryModel, table=True):
    """Current quota policy for an organization's deployment tier."""

    __tablename__ = "tier_quotas"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_tier_quotas_organization_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    tier_name: str = Field(default="hatchling")
    max_abilities: int = Field(default=5)
    max_storage_mb: int = Field(default=2048)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
