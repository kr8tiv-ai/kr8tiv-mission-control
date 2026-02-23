"""Schemas for task CRUD and task comment API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel

from app.schemas.common import NonEmptyStr
from app.schemas.tags import TagRef
from app.schemas.task_custom_fields import TaskCustomFieldValues

TaskStatus = Literal["inbox", "in_progress", "review", "done"]
TaskMode = Literal[
    "standard",
    "notebook",
    "arena",
    "arena_notebook",
    "notebook_creation",
]
NotebookProfile = Literal["enterprise", "personal", "auto"]
TaskIterationVerdict = Literal["APPROVED", "REVISE", "ERROR"]
STATUS_REQUIRED_ERROR = "status is required"
# Keep these symbols as runtime globals so Pydantic can resolve
# deferred annotations reliably.
RUNTIME_ANNOTATION_TYPES = (datetime, UUID, NonEmptyStr, TagRef)


class NotebookSources(SQLModel):
    """Notebook source payload used by notebook creation-capable task modes."""

    urls: list[str] = Field(default_factory=list)
    texts: list[str] = Field(default_factory=list)

    @field_validator("urls", mode="before")
    @classmethod
    def normalize_urls(cls, value: object) -> list[str]:
        """Normalize source URLs to a trimmed list."""
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for raw in value:
            if not isinstance(raw, str):
                continue
            url = raw.strip()
            if url:
                normalized.append(url)
        return normalized

    @field_validator("texts", mode="before")
    @classmethod
    def normalize_texts(cls, value: object) -> list[str]:
        """Normalize source text snippets to a trimmed list."""
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for raw in value:
            if not isinstance(raw, str):
                continue
            text = raw.strip()
            if text:
                normalized.append(text)
        return normalized


class ArenaConfig(SQLModel):
    """Mode-specific arena/notebook orchestration settings."""

    agents: list[str] = Field(default_factory=list)
    rounds: int = Field(default=1, ge=1, le=10)
    final_agent: str | None = None
    supermemory_enabled: bool = True
    sources: NotebookSources | None = None

    @field_validator("agents", mode="before")
    @classmethod
    def normalize_agents(cls, value: object) -> list[str]:
        """Normalize agent identifiers while preserving selection order."""
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for raw in value:
            if not isinstance(raw, str):
                continue
            agent_id = raw.strip().lower()
            if agent_id and agent_id not in normalized:
                normalized.append(agent_id)
        return normalized


class TaskBase(SQLModel):
    """Shared task fields used by task create/read payloads."""

    title: str
    description: str | None = None
    status: TaskStatus = "inbox"
    priority: str = "medium"
    task_mode: TaskMode = "standard"
    arena_config: ArenaConfig | None = None
    notebook_profile: NotebookProfile = "auto"
    notebook_id: str | None = None
    notebook_share_url: str | None = None
    due_at: datetime | None = None
    assigned_agent_id: UUID | None = None
    depends_on_task_ids: list[UUID] = Field(default_factory=list)
    tag_ids: list[UUID] = Field(default_factory=list)


class TaskCreate(TaskBase):
    """Payload for creating a task."""

    created_by_user_id: UUID | None = None
    custom_field_values: TaskCustomFieldValues = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mode_config(self) -> Self:
        """Require mode-specific fields for arena and notebook task modes."""
        mode = self.task_mode
        if mode in {"arena", "arena_notebook"}:
            if self.arena_config is None:
                raise ValueError("arena_config is required for arena task modes")
            if not self.arena_config.agents:
                raise ValueError("arena_config.agents must include at least one agent")
            if len(self.arena_config.agents) > 4:
                raise ValueError("arena_config.agents supports up to 4 agents")
            if not self.arena_config.final_agent:
                raise ValueError("arena_config.final_agent is required for arena task modes")
        if mode == "notebook_creation":
            if self.arena_config is None or self.arena_config.sources is None:
                raise ValueError("arena_config.sources is required for notebook creation mode")
            has_sources = bool(self.arena_config.sources.urls or self.arena_config.sources.texts)
            if not has_sources:
                raise ValueError(
                    "notebook creation mode requires at least one source URL or text snippet"
                )
        return self


class TaskUpdate(SQLModel):
    """Payload for partial task updates."""

    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: str | None = None
    task_mode: TaskMode | None = None
    arena_config: ArenaConfig | None = None
    notebook_profile: NotebookProfile | None = None
    notebook_id: str | None = None
    notebook_share_url: str | None = None
    due_at: datetime | None = None
    assigned_agent_id: UUID | None = None
    depends_on_task_ids: list[UUID] | None = None
    tag_ids: list[UUID] | None = None
    custom_field_values: TaskCustomFieldValues | None = None
    comment: NonEmptyStr | None = None

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: object) -> object | None:
        """Normalize blank comment strings to `None`."""
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        """Ensure explicitly supplied status is not null."""
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError(STATUS_REQUIRED_ERROR)
        return self


class TaskRead(TaskBase):
    """Task payload returned from read endpoints."""

    id: UUID
    board_id: UUID | None
    created_by_user_id: UUID | None
    in_progress_at: datetime | None
    created_at: datetime
    updated_at: datetime
    blocked_by_task_ids: list[UUID] = Field(default_factory=list)
    is_blocked: bool = False
    tags: list[TagRef] = Field(default_factory=list)
    custom_field_values: TaskCustomFieldValues | None = None


class TaskIterationRead(SQLModel):
    """Task iteration payload returned by arena iteration endpoints."""

    id: UUID
    task_id: UUID
    round_number: int
    agent_id: str
    output_text: str
    verdict: TaskIterationVerdict
    round_outputs: list[dict[str, object]] = Field(default_factory=list)
    created_at: datetime


class TaskNotebookQuery(SQLModel):
    """Notebook query payload for task-scoped NotebookLM interactions."""

    query: NonEmptyStr


class TaskNotebookQueryRead(SQLModel):
    """Notebook query response payload."""

    answer: str
    notebook_id: str


class TaskCommentCreate(SQLModel):
    """Payload for creating a task comment."""

    message: NonEmptyStr


class TaskCommentRead(SQLModel):
    """Task comment payload returned from read endpoints."""

    id: UUID
    message: str | None
    agent_id: UUID | None
    task_id: UUID | None
    created_at: datetime
