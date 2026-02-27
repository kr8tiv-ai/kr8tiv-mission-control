# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

from app.api.board_memory import _chat_targets, _sanitize_chat_snippet
from app.api.deps import ActorContext
from app.models.agents import Agent


def _agent(name: str, *, is_board_lead: bool = False) -> Agent:
    return Agent(
        name=name,
        gateway_id=uuid4(),
        board_id=uuid4(),
        openclaw_session_id=f"agent:{name.lower()}:main",
        is_board_lead=is_board_lead,
    )


def test_chat_targets_include_all_non_actor_agents() -> None:
    friday = _agent("Friday", is_board_lead=True)
    arsenal = _agent("Arsenal")
    edith = _agent("Edith")
    actor = ActorContext(actor_type="agent", agent=friday)

    targets = _chat_targets(
        agents=[friday, arsenal, edith],
        _mentions=set(),
        actor=actor,
    )

    assert set(targets.keys()) == {str(arsenal.id), str(edith.id)}


def test_sanitize_chat_snippet_redacts_sensitive_values() -> None:
    raw = (
        "AUTH_TOKEN=super-secret-token\n"
        "private_key: hidden-key\n"
        "Bearer very-secret-token\n"
        "3kP4x4v1o5GWEwPM4NfyWRhoX3N7Y8B5zUSBCf2VQ2q38He5FP8Ew5SyVMswwb47VPEB6odWbQqJ6R23"
    )

    sanitized = _sanitize_chat_snippet(raw)

    assert "super-secret-token" not in sanitized
    assert "hidden-key" not in sanitized
    assert "very-secret-token" not in sanitized
    assert "[REDACTED]" in sanitized
