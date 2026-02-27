from __future__ import annotations

from app.services.runtime.gsd_metrics_aggregator import aggregate_continuity_metrics


def test_aggregate_continuity_metrics_updates_recovery_and_retry_values() -> None:
    result = aggregate_continuity_metrics(
        existing={"retry_count": 1},
        total_incidents=4,
        recovered=3,
        failed=1,
        suppressed=0,
        retry_count=2,
    )

    assert result["incidents_total"] == 4
    assert result["incidents_recovered"] == 3
    assert result["incidents_failed"] == 1
    assert result["incidents_suppressed"] == 0
    assert result["retry_count"] == 2


def test_aggregate_continuity_metrics_computes_latency_and_rates() -> None:
    result = aggregate_continuity_metrics(
        existing={},
        latency_samples_ms=[120, 250, 310, 420, 510],
        tool_failures=2,
        tool_calls=20,
        gate_blocks=3,
        gate_checks=30,
    )

    assert result["latency_p95_ms"] == 510
    assert result["tool_failure_rate"] == 0.1
    assert result["gate_block_rate"] == 0.1
