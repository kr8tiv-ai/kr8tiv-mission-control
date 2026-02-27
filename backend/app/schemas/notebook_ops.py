"""Schemas for runtime NotebookLM capability-gate operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlmodel import SQLModel
from uuid import UUID


class NotebookCapabilityGateRead(SQLModel):
    """Current NotebookLM capability-gate status payload."""

    state: Literal["ready", "retryable", "misconfig", "hard_fail"]
    reason: str
    operator_message: str
    checked_at: datetime
    selected_profile: str | None = None
    notebook_count: int | None = None


class NotebookCapabilityGateSummaryRead(SQLModel):
    """Board-scoped summary of notebook capability-gate states."""

    board_id: UUID
    total_notebook_tasks: int
    gate_counts: dict[str, int]
