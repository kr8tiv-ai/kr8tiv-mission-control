"""Task iteration model for arena round persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class TaskIteration(TenantScoped, table=True):
    """Per-round iteration summary for arena and arena-notebook modes."""

    __tablename__ = "task_iterations"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    round_number: int = Field(default=1, index=True)
    agent_id: str = Field(index=True)
    output_text: str = Field(sa_column=Column(Text, nullable=False))
    verdict: str = Field(default="REVISE", index=True)
    round_outputs: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
