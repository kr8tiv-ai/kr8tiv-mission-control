"""Capability catalog entries for skills, libraries, and device access."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Capability(TenantScoped, table=True):
    """Organization-scoped capability catalog item."""

    __tablename__ = "capabilities"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "capability_type",
            "key",
            name="uq_capabilities_org_type_key",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    capability_type: str = Field(index=True)
    key: str = Field(index=True)
    name: str
    description: str | None = Field(default=None)
    version: str | None = Field(default=None)
    risk_level: str = Field(default="low")
    access_scope: str = Field(default="tenant")
    enabled: bool = Field(default=True)
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
