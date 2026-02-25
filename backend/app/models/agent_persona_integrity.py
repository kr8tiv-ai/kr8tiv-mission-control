"""Persistence model for agent persona checksum baselines and drift state."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class AgentPersonaIntegrity(QueryModel, table=True):
    """Stores the canonical persona-file checksums for an agent workspace."""

    __tablename__ = "agent_persona_integrity"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_agent_persona_integrity_agent_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    agent_id: UUID = Field(foreign_key="agents.id", index=True)
    soul_sha256: str
    user_sha256: str
    identity_sha256: str
    agents_sha256: str
    drift_count: int = Field(default=0)
    last_checked_at: datetime = Field(default_factory=utcnow)
    last_drift_at: datetime | None = Field(default=None)
    last_drift_fields: list[str] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
