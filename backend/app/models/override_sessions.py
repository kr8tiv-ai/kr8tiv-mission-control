"""Break-glass override sessions for emergency policy bypass workflows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class OverrideSession(QueryModel, table=True):
    """Scoped emergency override window for install/runtime governance actions."""

    __tablename__ = "override_sessions"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    started_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    reason: str
    expires_at: datetime
    active: bool = Field(default=True, index=True)
    ended_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
