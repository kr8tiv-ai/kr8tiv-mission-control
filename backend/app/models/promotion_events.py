"""Promotion and rollback event history for pack bindings."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class PromotionEvent(TenantScoped, table=True):
    """Audit trail for pack champion changes at any scope."""

    __tablename__ = "promotion_events"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID | None = Field(default=None, foreign_key="organizations.id", index=True)
    binding_id: UUID = Field(foreign_key="pack_bindings.id", index=True)

    event_type: str = Field(default="promote", index=True)
    from_pack_id: UUID | None = Field(default=None, foreign_key="prompt_packs.id", index=True)
    to_pack_id: UUID = Field(foreign_key="prompt_packs.id", index=True)
    triggered_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    reason: str | None = None

    metrics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
