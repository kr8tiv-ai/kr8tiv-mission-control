"""Prompt evolution control-plane models (registry, versions, telemetry, promotions)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped


class PromptPack(TenantScoped, table=True):
    """Board-scoped prompt/context pack with champion/challenger pointers."""

    __tablename__ = "prompt_packs"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    name: str = Field(index=True)
    scope: str = Field(default="board", index=True)
    target_agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)

    champion_version_id: UUID | None = Field(default=None, index=True)
    challenger_version_id: UUID | None = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PromptVersion(TenantScoped, table=True):
    """Versioned instruction/context artifact for a prompt pack."""

    __tablename__ = "prompt_versions"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    prompt_pack_id: UUID = Field(foreign_key="prompt_packs.id", index=True)
    version_number: int = Field(index=True)
    instruction_text: str = Field(sa_column=Column(Text))
    context_payload: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON))
    metrics_payload: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class TaskEvalScore(TenantScoped, table=True):
    """Task-level evaluation telemetry tied to optional prompt version lineage."""

    __tablename__ = "task_eval_scores"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    prompt_version_id: UUID | None = Field(default=None, foreign_key="prompt_versions.id", index=True)

    evaluator_type: str = Field(default="task_completion", index=True)
    score: float | None = None
    passed: bool | None = None
    detail_payload: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class OptimizationRun(TenantScoped, table=True):
    """Optimization run metadata and status for budgeted improvement cycles."""

    __tablename__ = "optimization_runs"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    prompt_pack_id: UUID | None = Field(default=None, foreign_key="prompt_packs.id", index=True)
    status: str = Field(default="queued", index=True)
    budget_limit_usd: float | None = None
    spend_usd: float = 0.0
    metadata_payload: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON))
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None


class PromotionEvent(TenantScoped, table=True):
    """Audit event for champion/challenger promotion decisions."""

    __tablename__ = "promotion_events"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    prompt_pack_id: UUID = Field(foreign_key="prompt_packs.id", index=True)
    from_version_id: UUID | None = Field(default=None, foreign_key="prompt_versions.id", index=True)
    to_version_id: UUID | None = Field(default=None, foreign_key="prompt_versions.id", index=True)
    decision: str = Field(default="approved", index=True)
    reason: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utcnow)
