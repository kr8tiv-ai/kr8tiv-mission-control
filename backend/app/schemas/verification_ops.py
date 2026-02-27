"""Schemas for runtime verification harness execution."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class VerificationCheckRead(SQLModel):
    """Serialized verification check outcome."""

    name: str
    required: bool
    passed: bool
    detail: str


class VerificationExecuteRead(SQLModel):
    """Response payload for verification harness execution."""

    generated_at: datetime
    all_passed: bool
    required_failed: int
    checks: list[VerificationCheckRead] = Field(default_factory=list)
    gsd_run_updated: bool = False
    evidence_link: str | None = None
