"""Tier quota policies for ability slots and storage limits."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class TierQuota(QueryModel, table=True):
    """Organization-scoped quota policy keyed by tier."""

    __tablename__ = "tier_quotas"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("organization_id", "tier", name="uq_tier_quotas_org_tier"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    tier: str = Field(default="personal", index=True)
    max_abilities: int = Field(default=25, ge=1)
    max_storage_mb: int = Field(default=1024, ge=1)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
