"""Run telemetry model for deterministic runtime evaluation inputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class RunTelemetry(TenantScoped, table=True):
    """Per-run runtime telemetry record submitted by harnesses and workers."""

    __tablename__ = "run_telemetry"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    board_id: UUID | None = Field(default=None, foreign_key="boards.id", index=True)
    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)
    task_id: UUID | None = Field(default=None, foreign_key="tasks.id", index=True)

    pack_id: UUID | None = Field(default=None, foreign_key="prompt_packs.id", index=True)
    pack_key: str = Field(index=True)
    tier: str = Field(default="personal", index=True)
    domain: str = Field(default="", index=True)
    run_ref: str = Field(default="", index=True)

    success_bool: bool = Field(default=False)
    retries: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    format_contract_passed: bool = Field(default=True)
    approval_gate_passed: bool = Field(default=True)

    checks: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    run_metadata: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON),
    )

    created_at: datetime = Field(default_factory=utcnow, index=True)
