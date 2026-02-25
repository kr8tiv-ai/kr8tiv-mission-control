"""Installation request records for capability and package governance."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class InstallationRequest(QueryModel, table=True):
    """Represents an install/uninstall request requiring governance checks."""

    __tablename__ = "installation_requests"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    capability_id: UUID | None = Field(default=None, foreign_key="capabilities.id", index=True)
    agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)
    requested_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    package_class: str = Field(index=True)
    package_key: str = Field(index=True)
    approval_mode: str = Field(default="ask_first", index=True)
    status: str = Field(default="pending_owner_approval", index=True)
    approved_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    approved_at: datetime | None = Field(default=None)
    denied_reason: str | None = Field(default=None)
    requested_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
