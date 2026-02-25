"""Customer change request records and lifecycle state."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class ChangeRequest(QueryModel, table=True):
    """Organization-scoped change request with triage and approval lifecycle."""

    __tablename__ = "change_requests"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    requested_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    requested_for_agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)
    title: str
    description: str
    category: str = Field(default="general", index=True)
    priority: str = Field(default="medium", index=True)
    status: str = Field(default="submitted", index=True)
    resolution_note: str | None = Field(default=None)
    reviewed_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    reviewed_at: datetime | None = Field(default=None)
    applied_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
