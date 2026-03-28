from __future__ import annotations


def classify_container_state(status: str, health: str | None) -> str:
    normalized_status = (status or "").lower()
    normalized_health = (health or "unknown").lower()

    if normalized_status != "running":
        return "restart_container"
    if normalized_health in {"unhealthy", "starting", "unknown"}:
        return "restart_container"
    return "noop"

