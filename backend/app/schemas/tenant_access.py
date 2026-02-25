"""Schemas for tenant self-access context endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel

_RUNTIME_TYPE_REFERENCES = (datetime, UUID)


class TenantOrganizationSummary(SQLModel):
    """Organization summary embedded in tenant self-access responses."""

    id: UUID
    name: str


class TenantMemberSummary(SQLModel):
    """Membership access summary for the current caller."""

    id: UUID
    user_id: UUID
    role: str
    all_boards_read: bool
    all_boards_write: bool


class TenantSelfAccessRead(SQLModel):
    """Tenant-scoped self-access context payload."""

    organization: TenantOrganizationSummary
    member: TenantMemberSummary
