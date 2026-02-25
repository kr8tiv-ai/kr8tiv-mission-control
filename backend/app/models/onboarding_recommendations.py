"""Persisted onboarding recommendations derived from onboarding Q&A drafts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class OnboardingRecommendation(QueryModel, table=True):
    """Stores recommendation output for a board onboarding session."""

    __tablename__ = "onboarding_recommendations"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    onboarding_session_id: UUID | None = Field(
        default=None,
        foreign_key="board_onboarding_sessions.id",
        index=True,
    )
    deployment_mode: str = Field(default="team", index=True)
    persona_preset_key: str = Field(default="team-operator", index=True)
    ability_bundle: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    voice_enabled: bool = Field(default=False)
    backup_options_enabled: bool = Field(default=True)
    notebooklm_optional: bool = Field(default=True)
    recommendation_notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
