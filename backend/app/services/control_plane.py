"""Core control-plane services for pack resolution, promotion, and deterministic scoring."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.models.deterministic_evals import DeterministicEval
from app.models.pack_bindings import PackBinding
from app.models.prompt_packs import PromptPack
from app.models.promotion_events import PromotionEvent
from app.models.run_telemetry import RunTelemetry

_SCOPE_PRIORITY = {
    "global": 1,
    "domain": 2,
    "organization": 3,
    "user": 4,
}
_ENGINEERING_REQUIRED_CHECKS = ("pr_created", "ci_passed", "human_reviewed")


@dataclass(frozen=True)
class ResolvedPackBinding:
    """Resolved binding result with champion pack and inheritance chain."""

    binding: PackBinding
    pack: PromptPack
    resolved_chain: list[str]


@dataclass(frozen=True)
class EvalSummary:
    """Aggregate deterministic eval metrics for promotion gates."""

    count: int
    avg_score: float
    hard_regressions: int


@dataclass(frozen=True)
class DeterministicScore:
    """Computed deterministic evaluation values for one run."""

    score: float
    latency_regression_pct: float
    approval_gate_compliance: bool
    hard_regression: bool
    details: dict[str, Any]


def normalize_scope_ref(scope: str, scope_ref: str | None, *, user_id: UUID | None = None) -> str:
    """Normalize scope-ref semantics for binding lookup and writes."""
    normalized = (scope_ref or "").strip()
    if scope == "user":
        if normalized:
            return normalized
        if user_id is None:
            msg = "scope_ref is required for user scope"
            raise ValueError(msg)
        return str(user_id)
    if scope == "domain":
        if not normalized:
            msg = "scope_ref is required for domain scope"
            raise ValueError(msg)
        return normalized
    return ""


def _scope_priority(scope: str) -> int:
    return _SCOPE_PRIORITY.get(scope, 0)


def is_engineering_swarm_run(run: RunTelemetry) -> bool:
    """Return whether deterministic done-gate should apply to this run."""
    if run.pack_key.strip().lower() in {"engineering-delivery-pack", "engineering"}:
        return True
    lane = str((run.run_metadata or {}).get("lane", "")).strip().lower()
    if lane in {"engineering", "engineering_swarm", "swarm_engineering"}:
        return True
    return False


def _passes_engineering_done_gate(checks: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for key in _ENGINEERING_REQUIRED_CHECKS:
        if not bool(checks.get(key)):
            missing.append(key)
    if bool(checks.get("ui_labeled")) and not bool(checks.get("ui_screenshot_present")):
        missing.append("ui_screenshot_present")
    return (len(missing) == 0, missing)


async def resolve_pack_binding(
    session: AsyncSession,
    *,
    organization_id: UUID,
    user_id: UUID | None,
    domain: str,
    tier: str,
    pack_key: str,
) -> ResolvedPackBinding | None:
    """Resolve champion pack using precedence user -> org -> domain -> global."""
    rows = list(
        await session.exec(
            select(PackBinding)
            .where(col(PackBinding.pack_key) == pack_key)
            .where(col(PackBinding.tier) == tier),
        )
    )
    if not rows:
        return None

    chain: list[tuple[str, PackBinding]] = []
    for row in rows:
        if row.scope == "global" and row.organization_id is None:
            chain.append(("global", row))
        elif row.scope == "domain" and row.organization_id is None and row.scope_ref == domain:
            chain.append(("domain", row))
        elif row.scope == "organization" and row.organization_id == organization_id:
            chain.append(("organization", row))
        elif (
            row.scope == "user"
            and user_id is not None
            and row.organization_id == organization_id
            and row.scope_ref == str(user_id)
        ):
            chain.append(("user", row))

    if not chain:
        return None

    chain.sort(
        key=lambda item: (
            _scope_priority(item[0]),
            item[1].updated_at,
        ),
    )
    _scope, winner = chain[-1]
    pack = await PromptPack.objects.by_id(winner.champion_pack_id).first(session)
    if pack is None:
        return None

    resolved_chain = [f"{scope}:{binding.id}" for scope, binding in chain]
    return ResolvedPackBinding(
        binding=winner,
        pack=pack,
        resolved_chain=resolved_chain,
    )


async def upsert_pack_binding(
    session: AsyncSession,
    *,
    organization_id: UUID | None,
    created_by_user_id: UUID | None,
    scope: str,
    scope_ref: str,
    tier: str,
    pack_key: str,
    champion_pack_id: UUID,
) -> tuple[PackBinding, UUID | None]:
    """Create or update champion binding and return previous champion if present."""
    organization_filter = (
        col(PackBinding.organization_id).is_(None)
        if organization_id is None
        else col(PackBinding.organization_id) == organization_id
    )
    row = (
        await session.exec(
            select(PackBinding)
            .where(organization_filter)
            .where(col(PackBinding.scope) == scope)
            .where(col(PackBinding.scope_ref) == scope_ref)
            .where(col(PackBinding.tier) == tier)
            .where(col(PackBinding.pack_key) == pack_key)
            .order_by(col(PackBinding.updated_at).desc())
            .limit(1)
        )
    ).first()

    now = utcnow()
    previous_pack_id: UUID | None = None
    if row is None:
        row = PackBinding(
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            scope=scope,
            scope_ref=scope_ref,
            tier=tier,
            pack_key=pack_key,
            champion_pack_id=champion_pack_id,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        return row, None

    previous_pack_id = row.champion_pack_id
    row.champion_pack_id = champion_pack_id
    row.updated_at = now
    if created_by_user_id is not None:
        row.created_by_user_id = created_by_user_id
    session.add(row)
    await session.flush()
    return row, previous_pack_id


async def record_promotion_event(
    session: AsyncSession,
    *,
    organization_id: UUID | None,
    binding_id: UUID,
    event_type: str,
    from_pack_id: UUID | None,
    to_pack_id: UUID,
    triggered_by_user_id: UUID | None,
    reason: str | None,
    metrics: dict[str, Any],
) -> PromotionEvent:
    """Persist one promotion/rollback audit event."""
    row = PromotionEvent(
        organization_id=organization_id,
        binding_id=binding_id,
        event_type=event_type,
        from_pack_id=from_pack_id,
        to_pack_id=to_pack_id,
        triggered_by_user_id=triggered_by_user_id,
        reason=reason,
        metrics=metrics,
        created_at=utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


async def eval_summary_for_pack(
    session: AsyncSession,
    *,
    organization_id: UUID,
    pack_id: UUID,
) -> EvalSummary:
    """Return aggregate deterministic eval summary for one pack."""
    rows = list(
        await session.exec(
            select(DeterministicEval)
            .where(col(DeterministicEval.organization_id) == organization_id)
            .where(col(DeterministicEval.pack_id) == pack_id),
        )
    )
    if not rows:
        return EvalSummary(count=0, avg_score=0.0, hard_regressions=0)
    count = len(rows)
    avg_score = sum(row.score for row in rows) / count
    hard_regressions = sum(1 for row in rows if row.hard_regression)
    return EvalSummary(count=count, avg_score=avg_score, hard_regressions=hard_regressions)


async def latest_non_current_pack_for_binding(
    session: AsyncSession,
    *,
    binding_id: UUID,
    current_pack_id: UUID,
) -> UUID | None:
    """Find previous champion from event history for rollback."""
    rows = list(
        await session.exec(
            select(PromotionEvent)
            .where(col(PromotionEvent.binding_id) == binding_id)
            .where(col(PromotionEvent.from_pack_id).is_not(None))
            .order_by(col(PromotionEvent.created_at).desc())
            .limit(20),
        )
    )
    for row in rows:
        if row.to_pack_id == current_pack_id and row.from_pack_id is not None:
            return row.from_pack_id
    return None


async def compute_deterministic_score(
    session: AsyncSession,
    *,
    run: RunTelemetry,
) -> DeterministicScore:
    """Compute deterministic score and regression flags from telemetry only."""
    baseline_candidates = list(
        await session.exec(
            select(RunTelemetry)
            .where(col(RunTelemetry.organization_id) == run.organization_id)
            .where(col(RunTelemetry.pack_key) == run.pack_key)
            .where(col(RunTelemetry.tier) == run.tier)
            .where(col(RunTelemetry.id) != run.id)
            .order_by(col(RunTelemetry.created_at).desc())
            .limit(50),
        )
    )
    baseline_latencies = [row.latency_ms for row in baseline_candidates if row.latency_ms > 0]
    baseline_latency = median(baseline_latencies) if baseline_latencies else max(1, run.latency_ms)

    latency_regression_pct = 0.0
    if baseline_latency > 0:
        latency_regression_pct = ((run.latency_ms - baseline_latency) / baseline_latency) * 100.0

    approval_gate_compliance = bool(run.approval_gate_passed)
    missing_checks: list[str] = []
    if is_engineering_swarm_run(run):
        done_gate_ok, missing_checks = _passes_engineering_done_gate(run.checks or {})
        approval_gate_compliance = approval_gate_compliance and done_gate_ok

    score = 0.0
    if run.success_bool:
        score += 55.0
    if run.format_contract_passed:
        score += 20.0
    if approval_gate_compliance:
        score += 20.0

    retry_penalty = min(float(max(run.retries, 0)) * 3.0, 15.0)
    score -= retry_penalty

    if latency_regression_pct > 0:
        score -= min(latency_regression_pct / 4.0, 10.0)
    else:
        score += min(abs(latency_regression_pct) / 10.0, 5.0)

    score = max(0.0, min(100.0, score))

    hard_regression = (
        (not run.success_bool)
        or (not run.format_contract_passed)
        or (not approval_gate_compliance)
        or latency_regression_pct >= 50.0
    )

    details: dict[str, Any] = {
        "baseline_latency_ms": baseline_latency,
        "required_checks": list(_ENGINEERING_REQUIRED_CHECKS) if is_engineering_swarm_run(run) else [],
        "missing_checks": missing_checks,
        "retry_penalty": retry_penalty,
    }

    return DeterministicScore(
        score=score,
        latency_regression_pct=float(latency_regression_pct),
        approval_gate_compliance=approval_gate_compliance,
        hard_regression=hard_regression,
        details=details,
    )


async def select_pack_for_scope(
    session: AsyncSession,
    *,
    scope: str,
    scope_ref: str,
    organization_id: UUID | None,
    tier: str,
    pack_key: str,
) -> PackBinding | None:
    """Select most recent binding row for exact scope tuple."""
    organization_filter = (
        col(PackBinding.organization_id).is_(None)
        if organization_id is None
        else col(PackBinding.organization_id) == organization_id
    )
    return (
        await session.exec(
            select(PackBinding)
            .where(organization_filter)
            .where(col(PackBinding.scope) == scope)
            .where(col(PackBinding.scope_ref) == scope_ref)
            .where(col(PackBinding.tier) == tier)
            .where(col(PackBinding.pack_key) == pack_key)
            .order_by(col(PackBinding.updated_at).desc())
            .limit(1),
        )
    ).first()
