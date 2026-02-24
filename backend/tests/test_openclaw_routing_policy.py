from __future__ import annotations

from app.services.openclaw.routing_policy import choose_agent


def test_routing_skips_degraded_agent_and_uses_fallback() -> None:
    selected = choose_agent(
        task_type="research",
        candidates=[
            {"id": "edith", "health": "degraded", "capable": True, "load": 1},
            {"id": "jocasta", "health": "healthy", "capable": True, "load": 2},
        ],
    )
    assert selected == "jocasta"


def test_routing_uses_load_when_health_is_equal() -> None:
    selected = choose_agent(
        task_type="implementation",
        candidates=[
            {"id": "arsenal", "health": "healthy", "capable": True, "load": 4},
            {"id": "edith", "health": "healthy", "capable": True, "load": 1},
        ],
    )
    assert selected == "edith"
