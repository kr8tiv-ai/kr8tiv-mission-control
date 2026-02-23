from __future__ import annotations

from app.api.tasks import _normalize_arena_config_for_storage
from app.schemas.tasks import ArenaConfig


def test_normalize_arena_config_filters_invalid_agents_and_injects_reviewer() -> None:
    normalized = _normalize_arena_config_for_storage(
        config=ArenaConfig(
            agents=["edith", "unknown", "friday"],
            rounds=3,
            final_agent="unknown",
            supermemory_enabled=True,
        ),
        task_mode="arena",
    )
    assert normalized is not None
    assert normalized["agents"] == ["edith", "friday", "arsenal"]
    assert normalized["final_agent"] == "edith"


def test_normalize_arena_config_does_not_inject_reviewer_for_non_arena_modes() -> None:
    normalized = _normalize_arena_config_for_storage(
        config=ArenaConfig(
            agents=["edith"],
            rounds=1,
            final_agent="edith",
        ),
        task_mode="notebook_creation",
    )
    assert normalized is not None
    assert normalized["agents"] == ["edith"]
