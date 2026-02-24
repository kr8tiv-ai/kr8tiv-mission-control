"""Deterministic evaluation records derived from run telemetry."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class DeterministicEval(TenantScoped, table=True):
    """Evaluation output row used by promotion gates and score trending."""

    __tablename__ = "deterministic_evals"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    run_telemetry_id: UUID = Field(foreign_key="run_telemetry.id", index=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    pack_id: UUID | None = Field(default=None, foreign_key="prompt_packs.id", index=True)

    pack_key: str = Field(index=True)
    tier: str = Field(default="personal", index=True)
    success_bool: bool = Field(default=False)
    retries: int = Field(default=0, ge=0)
    latency_regression_pct: float = Field(default=0.0)
    format_contract_compliance: bool = Field(default=True)
    approval_gate_compliance: bool = Field(default=True)
    score: float = Field(default=0.0)
    hard_regression: bool = Field(default=False)

    details: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
