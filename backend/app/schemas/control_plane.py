"""Control-plane API schemas for prompt packs, runtime telemetry, and promotions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import NonEmptyStr

ScopeLiteral = Literal["global", "domain", "organization", "user"]
TierLiteral = Literal["personal", "enterprise"]


class RuntimeRunIngestRequest(BaseModel):
    """Run telemetry envelope submitted by runtime harnesses."""

    board_id: UUID | None = None
    task_id: UUID | None = None
    pack_id: UUID | None = None
    pack_key: NonEmptyStr = "engineering-delivery-pack"
    tier: TierLiteral = "personal"
    domain: str | None = None
    run_ref: str | None = None

    success_bool: bool
    retries: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    format_contract_passed: bool = True
    approval_gate_passed: bool = True

    checks: dict[str, bool] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self) -> Self:
        """Normalize optional string fields for deterministic storage."""
        self.domain = (self.domain or "").strip() or None
        self.run_ref = (self.run_ref or "").strip() or None
        return self


class RuntimeRunIngestResponse(BaseModel):
    """Response payload for accepted telemetry ingestion."""

    run_id: UUID
    queued_for_eval: bool


class PromptPackCreateRequest(BaseModel):
    """Create a versioned prompt pack with optional champion binding."""

    pack_key: NonEmptyStr
    version: int = Field(default=1, ge=1)
    scope: ScopeLiteral = "organization"
    scope_ref: str | None = None
    tier: TierLiteral = "personal"
    description: str | None = None
    policy: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
    set_champion: bool = False

    @model_validator(mode="after")
    def validate_scope_ref(self) -> Self:
        """Require `scope_ref` for user/domain scoped packs."""
        normalized = (self.scope_ref or "").strip()
        if self.scope in {"user", "domain"} and not normalized:
            raise ValueError("scope_ref is required for user and domain scopes")
        self.scope_ref = normalized or None
        return self


class PromptPackRead(BaseModel):
    """Read model for prompt packs."""

    id: UUID
    organization_id: UUID | None
    scope: ScopeLiteral
    scope_ref: str
    tier: TierLiteral
    pack_key: str
    version: int
    description: str | None
    policy: dict[str, object]
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime


class PackResolutionResponse(BaseModel):
    """Resolved champion pack payload returned to runtimes."""

    binding_id: UUID
    prompt_pack_id: UUID
    scope: ScopeLiteral
    scope_ref: str
    tier: TierLiteral
    pack_key: str
    version: int
    policy: dict[str, object]
    resolved_chain: list[str] = Field(default_factory=list)


class PackPromotionRequest(BaseModel):
    """Promotion request body for advancing a challenger pack."""

    pack_key: NonEmptyStr
    scope: ScopeLiteral = "organization"
    scope_ref: str | None = None
    tier: TierLiteral = "personal"
    reason: str | None = None
    min_improvement_pct: float = Field(default=5.0, ge=0)
    require_zero_hard_regressions: bool = True
    force: bool = False

    @model_validator(mode="after")
    def normalize(self) -> Self:
        """Normalize scope_ref semantics for promotion lookups."""
        normalized = (self.scope_ref or "").strip()
        if self.scope in {"user", "domain"} and not normalized:
            raise ValueError("scope_ref is required for user and domain scopes")
        self.scope_ref = normalized or None
        return self


class PackRollbackRequest(BaseModel):
    """Rollback request body for reverting champion packs."""

    pack_key: NonEmptyStr
    scope: ScopeLiteral = "organization"
    scope_ref: str | None = None
    tier: TierLiteral = "personal"
    reason: str | None = None
    target_pack_id: UUID | None = None

    @model_validator(mode="after")
    def normalize(self) -> Self:
        """Normalize scope_ref semantics for rollback lookups."""
        normalized = (self.scope_ref or "").strip()
        if self.scope in {"user", "domain"} and not normalized:
            raise ValueError("scope_ref is required for user and domain scopes")
        self.scope_ref = normalized or None
        return self


class PackMutationResponse(BaseModel):
    """Response for promote/rollback operations."""

    binding_id: UUID
    previous_pack_id: UUID | None
    champion_pack_id: UUID
    promoted: bool
