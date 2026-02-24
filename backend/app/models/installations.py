"""Installation request records for managed capability execution."""

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
    """Managed installation request with approval/override status."""

    __tablename__ = "installation_requests"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    capability_id: UUID | None = Field(default=None, foreign_key="capabilities.id", index=True)
    title: str
    install_command: str
    approval_mode: str = Field(default="ask_first", index=True)
    status: str = Field(default="pending_owner_approval", index=True)
    requested_by_user_id: UUID | None = Field(default=None)
    override_session_id: UUID | None = Field(
        default=None,
        foreign_key="override_sessions.id",
        index=True,
    )
    requested_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
