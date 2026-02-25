"""Prompt pack model for mission-control managed prompt/context bundles."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class PromptPack(TenantScoped, table=True):
    """Versioned prompt/context package used by runtime scope bindings."""

    __tablename__ = "prompt_packs"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID | None = Field(default=None, foreign_key="organizations.id", index=True)
    created_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)

    scope: str = Field(default="organization", index=True)
    scope_ref: str = Field(default="", index=True)
    tier: str = Field(default="personal", index=True)
    pack_key: str = Field(index=True)
    version: int = Field(default=1, ge=1)
    description: str | None = None

    policy: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    pack_metadata: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON),
    )

    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)
