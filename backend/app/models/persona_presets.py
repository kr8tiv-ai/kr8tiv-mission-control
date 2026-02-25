"""Persona preset templates used to stamp agent identity and soul configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class PersonaPreset(TenantScoped, table=True):
    """Reusable preset for persona templates and identity-profile defaults."""

    __tablename__ = "persona_presets"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "key",
            name="uq_persona_presets_org_key",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    key: str = Field(index=True)
    name: str
    description: str | None = Field(default=None)
    deployment_mode: str = Field(default="team", index=True)
    identity_profile: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    identity_template: str | None = Field(default=None, sa_column=Column(Text))
    soul_template: str | None = Field(default=None, sa_column=Column(Text))
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
