"""Health-aware routing policy for OpenClaw task assignment."""

from __future__ import annotations

from typing import Any


def _health_rank(value: str) -> int:
    normalized = (value or "").strip().lower()
    if normalized == "healthy":
        return 3
    if normalized == "degraded":
        return 2
    if normalized == "unknown":
        return 1
    return 0


def choose_agent(
    *,
    task_type: str,
    candidates: list[dict[str, Any]],
    fallback_order: list[str] | None = None,
) -> str | None:
    """Choose the best agent for a task using health, load, and fallback order."""
    del task_type  # reserved for future task-type-specific weighting

    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        if not candidate.get("capable", False):
            continue
        if _health_rank(str(candidate.get("health", ""))) <= 0:
            continue
        eligible.append(candidate)

    if eligible:
        eligible.sort(
            key=lambda item: (
                -_health_rank(str(item.get("health", ""))),
                int(item.get("load", 0)),
            )
        )
        winner_id = eligible[0].get("id")
        return str(winner_id) if winner_id is not None else None

    if fallback_order:
        by_id = {str(item.get("id")): item for item in candidates if item.get("id") is not None}
        for fallback_id in fallback_order:
            fallback_candidate = by_id.get(fallback_id)
            if fallback_candidate is None:
                continue
            if fallback_candidate.get("capable", False):
                return fallback_id

    return None
