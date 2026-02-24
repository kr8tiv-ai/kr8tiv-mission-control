"""Organization-scoped persona preset catalog."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class PersonaPreset(QueryModel, table=True):
    """Reusable persona template bundle for applying to agents."""

    __tablename__ = "persona_presets"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_persona_presets_org_name"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    name: str = Field(index=True)
    description: str | None = Field(default=None)
    preset_mode: str = Field(default="team", index=True)
    identity_profile: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    identity_template: str | None = Field(default=None, sa_column=Column(Text))
    soul_template: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
