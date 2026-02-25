"""Disk pressure guardrail service for runtime safety decisions."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, Protocol

from app.core.time import utcnow

DiskSeverity = Literal["ok", "warning", "critical"]

DEFAULT_WARNING_THRESHOLD_PCT = 80.0
DEFAULT_CRITICAL_THRESHOLD_PCT = 90.0


class DiskUsageTuple(Protocol):
    """Protocol for values returned by ``shutil.disk_usage``."""

    total: int
    used: int
    free: int


DiskUsageReader = Callable[[str], DiskUsageTuple]


@dataclass(frozen=True, slots=True)
class DiskGuardStatus:
    """Computed disk guardrail envelope used by runtime operations APIs."""

    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    utilization_pct: float
    severity: DiskSeverity
    summary: str
    recommended_actions: list[str]
    checked_at: datetime
    warning_threshold_pct: float
    critical_threshold_pct: float


def _coerce_disk_usage(raw: DiskUsageTuple) -> tuple[int, int, int]:
    return int(raw.total), int(raw.used), int(raw.free)


def _calculate_utilization_pct(*, used: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((float(used) / float(total)) * 100.0, 2)


def _severity_for_pct(
    *,
    utilization_pct: float,
    warning_threshold_pct: float,
    critical_threshold_pct: float,
) -> DiskSeverity:
    if utilization_pct >= critical_threshold_pct:
        return "critical"
    if utilization_pct >= warning_threshold_pct:
        return "warning"
    return "ok"


def _recommended_actions_for_severity(severity: DiskSeverity) -> list[str]:
    if severity == "critical":
        return [
            "Immediate cleanup required to recover disk capacity.",
            "Pause non-essential deployments until free space is restored.",
            "Prune stale images, build artifacts, and oversized logs now.",
        ]
    if severity == "warning":
        return [
            "Schedule cleanup of stale images and historical logs.",
            "Review artifact retention policies before next rollout.",
        ]
    return ["Capacity is within guardrails; no immediate cleanup required."]


def _summary_for_severity(severity: DiskSeverity) -> str:
    if severity == "critical":
        return "Disk usage is above the critical threshold."
    if severity == "warning":
        return "Disk usage is above the warning threshold."
    return "Disk usage is within the safe operating range."


class DiskGuardService:
    """Compute disk pressure severity and action guidance."""

    def __init__(
        self,
        *,
        path: str = "/",
        warning_threshold_pct: float = DEFAULT_WARNING_THRESHOLD_PCT,
        critical_threshold_pct: float = DEFAULT_CRITICAL_THRESHOLD_PCT,
        usage_reader: DiskUsageReader | None = None,
    ) -> None:
        if warning_threshold_pct <= 0 or critical_threshold_pct <= 0:
            msg = "Disk guard thresholds must be positive percentages."
            raise ValueError(msg)
        if warning_threshold_pct >= critical_threshold_pct:
            msg = "warning_threshold_pct must be lower than critical_threshold_pct."
            raise ValueError(msg)
        self._path = path
        self._warning_threshold_pct = float(warning_threshold_pct)
        self._critical_threshold_pct = float(critical_threshold_pct)
        self._usage_reader = usage_reader or shutil.disk_usage

    def read_status(self) -> DiskGuardStatus:
        """Read current filesystem usage and classify pressure severity."""
        total, used, free = _coerce_disk_usage(self._usage_reader(self._path))
        utilization_pct = _calculate_utilization_pct(used=used, total=total)
        severity = _severity_for_pct(
            utilization_pct=utilization_pct,
            warning_threshold_pct=self._warning_threshold_pct,
            critical_threshold_pct=self._critical_threshold_pct,
        )
        return DiskGuardStatus(
            path=self._path,
            total_bytes=total,
            used_bytes=used,
            free_bytes=free,
            utilization_pct=utilization_pct,
            severity=severity,
            summary=_summary_for_severity(severity),
            recommended_actions=_recommended_actions_for_severity(severity),
            checked_at=utcnow(),
            warning_threshold_pct=self._warning_threshold_pct,
            critical_threshold_pct=self._critical_threshold_pct,
        )

