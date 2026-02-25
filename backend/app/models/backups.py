"""Customer-owned backup policy and reminder state records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class BackupPolicy(QueryModel, table=True):
    """Organization-scoped backup reminder and confirmation policy state."""

    __tablename__ = "backup_policies"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("organization_id", name="uq_backup_policies_org"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    owner_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    status: str = Field(default="unconfirmed", index=True)
    destination_type: str | None = Field(default=None, index=True)
    destination_label: str | None = Field(default=None)
    warning_shown_at: datetime | None = Field(default=None)
    last_prompted_at: datetime | None = Field(default=None)
    next_prompt_at: datetime | None = Field(default=None)
    last_confirmed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
