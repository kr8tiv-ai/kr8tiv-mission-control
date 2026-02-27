"""Runtime operations endpoints for safety guardrail surfaces."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Field, SQLModel, col, select

from app.api.deps import require_admin_or_agent, require_org_admin
from app.core.config import settings
from app.core.time import utcnow
from app.db.session import get_session
from app.models.boards import Board
from app.models.gsd_runs import GSDRun
from app.models.tasks import Task
from app.services.notebooklm_capability_gate import evaluate_notebooklm_capability
from app.services.organizations import OrganizationContext
from app.services.runtime.disk_guard import DiskGuardService
from app.services.runtime.verification_harness import run_verification_harness

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/runtime/ops", tags=["control-plane"])
ACTOR_DEP = Depends(require_admin_or_agent)
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)
PATH_QUERY = Query(default="/")
BOARD_ID_QUERY = Query(default=None)
PROFILE_QUERY = Query(default="auto")
NOTEBOOK_ENABLED_MODES = ("notebook", "arena_notebook", "notebook_creation")
_NOTEBOOK_STATE_KEYS = ("ready", "retryable", "misconfig", "hard_fail", "unknown")


class RuntimeDiskGuardThresholdsRead(SQLModel):
    """Threshold values used for disk pressure severity mapping."""

    warning_pct: float
    critical_pct: float


class RuntimeDiskGuardRead(SQLModel):
    """Runtime disk guardrail status envelope."""

    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    utilization_pct: float
    severity: Literal["ok", "warning", "critical"]
    summary: str
    recommended_actions: list[str]
    checked_at: datetime
    thresholds: RuntimeDiskGuardThresholdsRead = Field(
        description="Configured severity thresholds.",
    )


class RuntimeArenaStatusRead(SQLModel):
    """Arena orchestration configuration and health summary."""

    configured_agents: list[str]
    reviewer_agent: str
    reviewer_in_allowlist: bool
    healthy: bool
    summary: str


class RuntimeNotebookStatusRead(SQLModel):
    """Notebook capability-gate health and optional board-scoped counts."""

    state: Literal["ready", "retryable", "misconfig", "hard_fail"]
    reason: str
    operator_message: str
    checked_at: datetime
    selected_profile: str | None = None
    notebook_count: int | None = None
    total_notebook_tasks: int | None = None
    gate_counts: dict[str, int] | None = None


class RuntimeVerificationCheckRead(SQLModel):
    """Verification harness check entry."""

    name: str
    required: bool
    passed: bool
    detail: str


class RuntimeVerificationStatusRead(SQLModel):
    """Verification harness aggregate status."""

    all_passed: bool
    required_failed: int
    checks: list[RuntimeVerificationCheckRead]
    failed_check_names: list[str]
    checked_at: datetime


class RuntimeGSDGateStatusRead(SQLModel):
    """Latest GSD gate status for rollout progression visibility."""

    latest_run_id: UUID | None = None
    latest_stage: str | None = None
    latest_status: str | None = None
    verification_required_failed: int | None = None
    is_blocked: bool
    updated_at: datetime | None = None
    summary: str


class RuntimeControlPlaneStatusRead(SQLModel):
    """Unified control-plane status surface for operators."""

    checked_at: datetime
    board_id: UUID | None = None
    arena: RuntimeArenaStatusRead
    notebook: RuntimeNotebookStatusRead
    verification: RuntimeVerificationStatusRead
    gsd: RuntimeGSDGateStatusRead


def _collect_route_paths(request: Request) -> set[str]:
    return {
        str(route.path)
        for route in request.app.routes
        if hasattr(route, "path")
    }


def _build_arena_status() -> RuntimeArenaStatusRead:
    configured_agents = list(settings.allowed_arena_agent_ids())
    reviewer_agent = settings.arena_reviewer_agent.strip().lower()
    reviewer_in_allowlist = reviewer_agent in configured_agents if reviewer_agent else False
    healthy = bool(configured_agents) and reviewer_in_allowlist
    summary = (
        "Arena routing configured."
        if healthy
        else "Arena configuration is degraded: reviewer missing from allowlist or no agents configured."
    )
    return RuntimeArenaStatusRead(
        configured_agents=configured_agents,
        reviewer_agent=reviewer_agent,
        reviewer_in_allowlist=reviewer_in_allowlist,
        healthy=healthy,
        summary=summary,
    )


def _as_notebook_counts(states: list[str | None]) -> tuple[int, dict[str, int]]:
    counts = {key: 0 for key in _NOTEBOOK_STATE_KEYS}
    for state in states:
        normalized = str(state or "").strip().lower()
        if normalized in counts and normalized != "unknown":
            counts[normalized] += 1
        else:
            counts["unknown"] += 1
    return len(states), counts


def _coerce_required_failed(snapshot: dict[str, object]) -> int | None:
    raw = snapshot.get("verification_required_failed")
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, (int, float)):
        return int(raw)
    return None


async def _get_latest_gsd_gate_status(
    *,
    session: AsyncSession,
    organization_id: UUID,
    board_id: UUID | None,
) -> RuntimeGSDGateStatusRead:
    statement = (
        select(GSDRun)
        .where(col(GSDRun.organization_id) == organization_id)
        .order_by(col(GSDRun.updated_at).desc(), col(GSDRun.created_at).desc())
        .limit(1)
    )
    if board_id is not None:
        statement = statement.where(col(GSDRun.board_id) == board_id)
    row = (await session.exec(statement)).first()
    if row is None:
        return RuntimeGSDGateStatusRead(
            is_blocked=False,
            summary="No GSD runs found for requested scope.",
        )
    required_failed = _coerce_required_failed(dict(row.metrics_snapshot))
    is_blocked = str(row.status).strip().lower() == "blocked"
    summary = "Latest GSD run is blocked." if is_blocked else "Latest GSD run is not blocked."
    return RuntimeGSDGateStatusRead(
        latest_run_id=row.id,
        latest_stage=row.stage,
        latest_status=row.status,
        verification_required_failed=required_failed,
        is_blocked=is_blocked,
        updated_at=row.updated_at,
        summary=summary,
    )


@router.get("/disk-guard", response_model=RuntimeDiskGuardRead)
async def runtime_disk_guard(
    path: str = PATH_QUERY,
    _actor: object = ACTOR_DEP,
) -> RuntimeDiskGuardRead:
    """Return current disk pressure classification and recommended actions."""
    status = DiskGuardService(path=path).read_status()
    return RuntimeDiskGuardRead(
        path=status.path,
        total_bytes=status.total_bytes,
        used_bytes=status.used_bytes,
        free_bytes=status.free_bytes,
        utilization_pct=status.utilization_pct,
        severity=status.severity,
        summary=status.summary,
        recommended_actions=status.recommended_actions,
        checked_at=status.checked_at,
        thresholds=RuntimeDiskGuardThresholdsRead(
            warning_pct=status.warning_threshold_pct,
            critical_pct=status.critical_threshold_pct,
        ),
    )


@router.get("/control-plane-status", response_model=RuntimeControlPlaneStatusRead)
async def runtime_control_plane_status(
    request: Request,
    board_id: UUID | None = BOARD_ID_QUERY,
    profile: str = PROFILE_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> RuntimeControlPlaneStatusRead:
    """Return unified runtime status for arena, notebook, verification, and GSD gate."""
    if board_id is not None:
        board = await Board.objects.by_id(board_id).first(session)
        if board is None or board.organization_id != ctx.organization.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    notebook_gate = await evaluate_notebooklm_capability(
        profile=profile,
        require_notebook=False,
    )
    verification = await run_verification_harness(
        route_paths=_collect_route_paths(request),
        profile=profile,
    )

    total_notebook_tasks: int | None = None
    gate_counts: dict[str, int] | None = None
    if board_id is not None:
        states = (
            await session.exec(
                select(col(Task.notebook_gate_state))
                .where(col(Task.board_id) == board_id)
                .where(col(Task.task_mode).in_(NOTEBOOK_ENABLED_MODES))
            )
        ).all()
        total_notebook_tasks, gate_counts = _as_notebook_counts(states)

    failed_checks = [check.name for check in verification.checks if not check.passed]
    return RuntimeControlPlaneStatusRead(
        checked_at=utcnow(),
        board_id=board_id,
        arena=_build_arena_status(),
        notebook=RuntimeNotebookStatusRead(
            state=notebook_gate.state,
            reason=notebook_gate.reason,
            operator_message=notebook_gate.operator_message,
            checked_at=notebook_gate.checked_at,
            selected_profile=notebook_gate.selected_profile,
            notebook_count=notebook_gate.notebook_count,
            total_notebook_tasks=total_notebook_tasks,
            gate_counts=gate_counts,
        ),
        verification=RuntimeVerificationStatusRead(
            all_passed=verification.all_passed,
            required_failed=verification.required_failed,
            checks=[
                RuntimeVerificationCheckRead(
                    name=check.name,
                    required=check.required,
                    passed=check.passed,
                    detail=check.detail,
                )
                for check in verification.checks
            ],
            failed_check_names=failed_checks,
            checked_at=verification.generated_at,
        ),
        gsd=await _get_latest_gsd_gate_status(
            session=session,
            organization_id=ctx.organization.id,
            board_id=board_id,
        ),
    )
