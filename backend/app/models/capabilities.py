"""Capability catalog models for skills, libraries, and device access."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Capability(QueryModel, table=True):
    """Organization-scoped capability record (skill/library/device)."""

    __tablename__ = "capabilities"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "kind",
            "name",
            name="uq_capabilities_org_kind_name",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    kind: str = Field(index=True)
    name: str = Field(index=True)
    description: str | None = Field(default=None)
    risk_level: str = Field(default="medium", index=True)
    scope: str = Field(default="team", index=True)
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
