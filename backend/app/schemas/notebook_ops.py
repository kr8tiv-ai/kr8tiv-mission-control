"""Schemas for runtime NotebookLM capability-gate operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlmodel import SQLModel


class NotebookCapabilityGateRead(SQLModel):
    """Current NotebookLM capability-gate status payload."""

    state: Literal["ready", "retryable", "misconfig", "hard_fail"]
    reason: str
    operator_message: str
    checked_at: datetime
    selected_profile: str | None = None
    notebook_count: int | None = None

