"""Schemas for installation request governance and break-glass overrides."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel

from app.schemas.common import NonEmptyStr

_RUNTIME_TYPE_REFERENCES = (datetime, UUID, NonEmptyStr)

ApprovalMode = Literal["ask_first", "auto"]
InstallationStatus = Literal["pending_owner_approval", "approved", "executed"]


class InstallationRequestCreate(SQLModel):
    """Payload for creating installation requests."""

    capability_id: UUID | None = None
    title: NonEmptyStr
    install_command: NonEmptyStr
    approval_mode: ApprovalMode = "ask_first"
    requested_payload: dict[str, object] = Field(default_factory=dict)


class InstallationRequestRead(SQLModel):
    """Read model for installation requests."""

    id: UUID
    organization_id: UUID
    capability_id: UUID | None = None
    title: str
    install_command: str
    approval_mode: ApprovalMode
    status: InstallationStatus
    override_session_id: UUID | None = None
    requested_payload: dict[str, object]
    created_at: datetime
    updated_at: datetime


class OverrideSessionCreate(SQLModel):
    """Payload for creating break-glass override sessions."""

    reason: NonEmptyStr
    ttl_minutes: int = Field(ge=1, le=1440)


class OverrideSessionRead(SQLModel):
    """Read model for override sessions."""

    id: UUID
    organization_id: UUID
    reason: str
    expires_at: datetime
    active: bool
    created_at: datetime
    updated_at: datetime


class InstallationExecuteRequest(SQLModel):
    """Payload for executing an installation request."""

    override_session_id: UUID | None = None


class InstallationExecuteResponse(SQLModel):
    """Execution response for an installation request."""

    executed: bool
    request_id: UUID
    status: InstallationStatus
