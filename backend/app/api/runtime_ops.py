"""Runtime operations endpoints for safety guardrail surfaces."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlmodel import Field, SQLModel

from app.api.deps import require_admin_or_agent
from app.services.runtime.disk_guard import DiskGuardService

router = APIRouter(prefix="/runtime/ops", tags=["control-plane"])
ACTOR_DEP = Depends(require_admin_or_agent)
PATH_QUERY = Query(default="/")


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

