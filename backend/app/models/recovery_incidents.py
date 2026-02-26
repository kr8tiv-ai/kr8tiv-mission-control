"""Persistence model for runtime agent recovery incidents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class RecoveryIncident(QueryModel, table=True):
    """A detected continuity incident and the system's recovery outcome."""

    __tablename__ = "recovery_incidents"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    board_id: UUID | None = Field(default=None, foreign_key="boards.id", index=True)
    agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)
    status: str = Field(default="detected", index=True)
    reason: str = Field(index=True)
    action: str | None = Field(default=None)
    attempts: int = Field(default=0)
    last_error: str | None = Field(default=None)
    detected_at: datetime = Field(default_factory=utcnow, index=True)
    recovered_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
