"""Schemas for persona integrity checksum and drift reporting."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel

_RUNTIME_TYPE_REFERENCES = (datetime, UUID)


class PersonaIntegrityHashes(SQLModel):
    """Checksum bundle for the four persona-governing files."""

    soul_sha256: str
    user_sha256: str
    identity_sha256: str
    agents_sha256: str


class PersonaIntegrityCheckResult(SQLModel):
    """Result payload emitted by persona integrity verification."""

    agent_id: UUID
    baseline_created: bool = False
    drift_detected: bool = False
    drift_fields: list[str] = Field(default_factory=list)
    drift_count: int = 0
    baseline: PersonaIntegrityHashes
    current: PersonaIntegrityHashes


class PersonaIntegrityRecord(SQLModel):
    """Materialized row payload for persisted persona integrity state."""

    id: UUID
    agent_id: UUID
    drift_count: int
    last_checked_at: datetime
    last_drift_at: datetime | None = None
    last_drift_fields: list[str] | None = None
    baseline: PersonaIntegrityHashes
