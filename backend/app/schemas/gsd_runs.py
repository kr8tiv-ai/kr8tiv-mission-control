"""Schemas for GSD run stage telemetry APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import NonEmptyStr

GSDRunStage = Literal["planning", "implementation", "rollout", "validation", "hardening"]
GSDRunStatus = Literal["queued", "in_progress", "blocked", "completed"]
OwnerApprovalStatus = Literal["not_required", "pending", "approved", "rejected"]
GSDMetricsValue = int | float


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_links(values: list[str]) -> list[str]:
    normalized = [entry.strip() for entry in values if entry.strip()]
    # Preserve order while removing duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in normalized:
        if entry in seen:
            continue
        ordered.append(entry)
        seen.add(entry)
    return ordered


def _normalize_metrics(values: dict[str, GSDMetricsValue]) -> dict[str, GSDMetricsValue]:
    normalized: dict[str, GSDMetricsValue] = {}
    for raw_key, value in values.items():
        key = raw_key.strip()
        if not key:
            continue
        normalized[key] = value
    return normalized


class GSDRunCreate(BaseModel):
    """Payload for creating a GSD run telemetry record."""

    board_id: UUID | None = None
    task_id: UUID | None = None
    run_name: str | None = None
    iteration_number: int = Field(default=1, ge=1)
    stage: GSDRunStage = "planning"
    status: GSDRunStatus = "in_progress"
    owner_approval_required: bool = False
    owner_approval_status: OwnerApprovalStatus | None = None
    owner_approval_note: str | None = None
    rollout_evidence_links: list[NonEmptyStr] = Field(default_factory=list)
    metrics_snapshot: dict[str, GSDMetricsValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self) -> Self:
        """Normalize text/link payload fields."""
        self.run_name = _normalize_optional_text(self.run_name)
        self.owner_approval_note = _normalize_optional_text(self.owner_approval_note)
        self.rollout_evidence_links = _normalize_links(self.rollout_evidence_links)
        self.metrics_snapshot = _normalize_metrics(self.metrics_snapshot)
        return self


class GSDRunUpdate(BaseModel):
    """Patch payload for stage/status/evidence updates."""

    stage: GSDRunStage | None = None
    status: GSDRunStatus | None = None
    owner_approval_required: bool | None = None
    owner_approval_status: OwnerApprovalStatus | None = None
    owner_approval_note: str | None = None
    rollout_evidence_links: list[NonEmptyStr] | None = None
    metrics_snapshot: dict[str, GSDMetricsValue] | None = None
    run_name: str | None = None
    iteration_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def normalize(self) -> Self:
        """Normalize optional payload fields when provided."""
        self.owner_approval_note = _normalize_optional_text(self.owner_approval_note)
        self.run_name = _normalize_optional_text(self.run_name)
        if self.rollout_evidence_links is not None:
            self.rollout_evidence_links = _normalize_links(self.rollout_evidence_links)
        if self.metrics_snapshot is not None:
            self.metrics_snapshot = _normalize_metrics(self.metrics_snapshot)
        return self


class GSDRunRead(BaseModel):
    """Read model for persisted GSD run telemetry."""

    id: UUID
    organization_id: UUID
    board_id: UUID | None = None
    task_id: UUID | None = None
    created_by_user_id: UUID | None = None
    run_name: str
    iteration_number: int
    stage: GSDRunStage
    status: GSDRunStatus
    owner_approval_required: bool
    owner_approval_status: OwnerApprovalStatus
    owner_approval_note: str | None = None
    owner_approved_at: datetime | None = None
    rollout_evidence_links: list[str]
    metrics_snapshot: dict[str, GSDMetricsValue]
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
