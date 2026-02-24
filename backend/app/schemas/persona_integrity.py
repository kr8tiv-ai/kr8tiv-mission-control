"""Schemas for persona-integrity baseline and drift checks."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel

_RUNTIME_TYPE_REFERENCES = (datetime, UUID)


class PersonaIntegrityBaselineRead(SQLModel):
    """Persisted baseline checksum record for one agent."""

    id: UUID
    agent_id: UUID
    soul_sha256: str
    user_sha256: str
    identity_sha256: str
    agents_sha256: str
    drift_count: int
    last_checked_at: datetime
    last_drift_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PersonaIntegrityDriftResult(SQLModel):
    """Result payload for a drift check against the baseline."""

    agent_id: UUID
    has_drift: bool
    drifted_files: list[str]
