"""Break-glass override sessions for controlled installation execution."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class OverrideSession(QueryModel, table=True):
    """Time-bounded override session with explicit reason."""

    __tablename__ = "override_sessions"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    reason: str
    expires_at: datetime = Field(index=True)
    active: bool = Field(default=True, index=True)
    created_by_user_id: UUID | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
