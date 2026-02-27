"""GSD run telemetry model for stage-level execution tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class GSDRun(TenantScoped, table=True):
    """Per-run GSD stage telemetry and owner-approval tracking."""

    __tablename__ = "gsd_runs"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    board_id: UUID | None = Field(default=None, foreign_key="boards.id", index=True)
    task_id: UUID | None = Field(default=None, foreign_key="tasks.id", index=True)
    created_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)

    run_name: str = Field(default="", index=True)
    iteration_number: int = Field(default=1, ge=1, index=True)
    stage: str = Field(default="planning", index=True)
    status: str = Field(default="in_progress", index=True)

    owner_approval_required: bool = Field(default=False)
    owner_approval_status: str = Field(default="not_required", index=True)
    owner_approval_note: str | None = None
    owner_approved_at: datetime | None = None
    rollout_evidence_links: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    metrics_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )

    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)
