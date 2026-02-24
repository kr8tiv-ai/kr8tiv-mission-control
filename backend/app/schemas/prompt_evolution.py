"""Schema models for prompt evolution control-plane APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PromptPackCreate(BaseModel):
    """Create payload for a prompt pack."""

    name: str = Field(min_length=1, max_length=120)
    scope: str = Field(default="board", min_length=1, max_length=64)
    target_agent_id: UUID | None = None


class PromptPackRead(BaseModel):
    """Serialized prompt pack."""

    id: UUID
    board_id: UUID
    name: str
    scope: str
    target_agent_id: UUID | None = None
    champion_version_id: UUID | None = None
    challenger_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class PromptVersionCreate(BaseModel):
    """Create payload for a prompt version."""

    instruction_text: str = Field(min_length=1)
    context_payload: dict[str, object] = Field(default_factory=dict)
    metrics_payload: dict[str, object] = Field(default_factory=dict)
    set_as_challenger: bool = True


class PromptVersionRead(BaseModel):
    """Serialized prompt version."""

    id: UUID
    prompt_pack_id: UUID
    version_number: int
    instruction_text: str
    context_payload: dict[str, object]
    metrics_payload: dict[str, object]
    created_at: datetime


class PromotionRequest(BaseModel):
    """Manual promotion gate request."""

    to_version_id: UUID
    reason: str | None = None
    force: bool = False


class PromotionEventRead(BaseModel):
    """Serialized promotion event."""

    id: UUID
    board_id: UUID
    prompt_pack_id: UUID
    from_version_id: UUID | None = None
    to_version_id: UUID | None = None
    decision: str
    reason: str | None = None
    created_at: datetime


class TaskEvalScoreRead(BaseModel):
    """Serialized task evaluation telemetry."""

    id: UUID
    board_id: UUID
    task_id: UUID
    prompt_version_id: UUID | None = None
    evaluator_type: str
    score: float | None = None
    passed: bool | None = None
    detail_payload: dict[str, object]
    created_at: datetime
