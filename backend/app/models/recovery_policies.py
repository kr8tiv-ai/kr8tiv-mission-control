"""Runtime recovery policy configuration per organization."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class RecoveryPolicy(QueryModel, table=True):
    """Organization-scoped policy controlling automated agent recovery behavior."""

    __tablename__ = "recovery_policies"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("organization_id", name="uq_recovery_policies_org"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    enabled: bool = Field(default=True, index=True)
    stale_after_seconds: int = Field(default=900)
    max_restarts_per_hour: int = Field(default=3)
    cooldown_seconds: int = Field(default=300)
    alert_dedupe_seconds: int = Field(default=900)
    alert_telegram: bool = Field(default=True)
    alert_whatsapp: bool = Field(default=True)
    alert_ui: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
