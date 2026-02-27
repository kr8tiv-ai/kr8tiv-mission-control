"""Helpers for normalizing and aggregating GSD continuity metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


MetricsValue = int | float


def _p95(samples: Sequence[int]) -> int:
    ordered = sorted(int(value) for value in samples)
    if not ordered:
        return 0
    rank = max(1, math.ceil(0.95 * len(ordered)))
    return ordered[min(len(ordered), rank) - 1]


def aggregate_continuity_metrics(
    *,
    existing: Mapping[str, MetricsValue] | None,
    total_incidents: int | None = None,
    recovered: int | None = None,
    failed: int | None = None,
    suppressed: int | None = None,
    retry_count: int | None = None,
    latency_samples_ms: Sequence[int] | None = None,
    tool_failures: int | None = None,
    tool_calls: int | None = None,
    gate_blocks: int | None = None,
    gate_checks: int | None = None,
) -> dict[str, MetricsValue]:
    """Return a normalized metrics snapshot by applying provided continuity inputs."""
    snapshot: dict[str, MetricsValue] = dict(existing or {})

    if total_incidents is not None:
        snapshot["incidents_total"] = int(max(0, total_incidents))
    if recovered is not None:
        snapshot["incidents_recovered"] = int(max(0, recovered))
    if failed is not None:
        snapshot["incidents_failed"] = int(max(0, failed))
    if suppressed is not None:
        snapshot["incidents_suppressed"] = int(max(0, suppressed))
    if retry_count is not None:
        snapshot["retry_count"] = int(max(0, retry_count))

    normalized_samples = [int(value) for value in (latency_samples_ms or []) if int(value) >= 0]
    if normalized_samples:
        snapshot["latency_p95_ms"] = _p95(normalized_samples)

    if tool_failures is not None and tool_calls is not None and tool_calls > 0:
        snapshot["tool_failure_rate"] = round(max(0.0, float(tool_failures)) / float(tool_calls), 4)

    if gate_blocks is not None and gate_checks is not None and gate_checks > 0:
        snapshot["gate_block_rate"] = round(max(0.0, float(gate_blocks)) / float(gate_checks), 4)

    return snapshot
