"""Persisted onboarding recommendations for board/persona setup."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class OnboardingRecommendation(QueryModel, table=True):
    """Recommendation output from onboarding Q&A for board setup."""

    __tablename__ = "onboarding_recommendations"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("board_id", name="uq_onboarding_recommendations_board_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    onboarding_session_id: UUID | None = Field(
        default=None,
        foreign_key="board_onboarding_sessions.id",
        index=True,
    )
    deployment_mode: str = Field(default="team", index=True)
    recommended_preset: str = Field(default="team_orchestrated_default")
    capabilities: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    voice_enabled: bool = Field(default=False)
    computer_automation_profile: str | None = Field(default=None)
    supermemory_plugin_command: str = Field(
        default="openclaw plugins install @supermemory/openclaw-supermemory",
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
