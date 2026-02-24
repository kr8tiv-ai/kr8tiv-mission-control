"""Pack binding model for champion pack resolution by scope."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class PackBinding(TenantScoped, table=True):
    """Resolved champion pack pointer for a given scope/tier/pack key."""

    __tablename__ = "pack_bindings"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID | None = Field(default=None, foreign_key="organizations.id", index=True)
    created_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)

    scope: str = Field(default="organization", index=True)
    scope_ref: str = Field(default="", index=True)
    tier: str = Field(default="personal", index=True)
    pack_key: str = Field(index=True)
    champion_pack_id: UUID = Field(foreign_key="prompt_packs.id", index=True)

    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)
