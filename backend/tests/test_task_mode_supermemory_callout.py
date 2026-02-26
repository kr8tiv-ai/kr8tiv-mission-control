# ruff: noqa: S101
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import task_mode_execution
from app.services.task_mode_execution import _ModeExecutionContext


class _DummySession:
    def __init__(self) -> None:
        self.items: list[object] = []

    def add(self, item: object) -> None:
        self.items.append(item)


def _ctx(*, supermemory_enabled: bool, rounds: int = 1) -> _ModeExecutionContext:
    task = SimpleNamespace(
        id=uuid4(),
        title="Investigate issue",
        description="Need reliable fix path",
        arena_config={
            "agents": ["arsenal"],
            "rounds": rounds,
            "final_agent": "arsenal",
            "supermemory_enabled": supermemory_enabled,
        },
        task_mode="arena",
        notebook_profile="auto",
    )
    return _ModeExecutionContext(
        board=SimpleNamespace(id=uuid4()),
        task=task,
        gateway_config=object(),
        allowed_agents=("arsenal",),
        reviewer_agent="arsenal",
    )


@pytest.mark.asyncio
async def test_arena_mode_injects_supermemory_context_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    session = _DummySession()
    ctx = _ctx(supermemory_enabled=True)

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    async def _fake_retrieve_context(**_kwargs):
        return ["Known incident from yesterday."]

    async def _fake_run_agent_turn(**kwargs):
        prompt = str(kwargs["prompt"])
        prompts.append(prompt)
        if "VERDICT" not in prompt:
            return "arsenal", "VERDICT: APPROVED"
        return "arsenal", "final output"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(
        task_mode_execution,
        "retrieve_arena_context_lines",
        _fake_retrieve_context,
    )
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)

    assert any("Supermemory context:" in prompt for prompt in prompts)
    assert any("- Known incident from yesterday." in prompt for prompt in prompts)


@pytest.mark.asyncio
async def test_arena_mode_skips_supermemory_context_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    session = _DummySession()
    ctx = _ctx(supermemory_enabled=False)

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    async def _fake_run_agent_turn(**kwargs):
        prompt = str(kwargs["prompt"])
        prompts.append(prompt)
        if "VERDICT" not in prompt:
            return "arsenal", "VERDICT: APPROVED"
        return "arsenal", "final output"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)

    assert all("Supermemory context:" not in prompt for prompt in prompts)


@pytest.mark.asyncio
async def test_arena_mode_continues_when_supermemory_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _DummySession()
    ctx = _ctx(supermemory_enabled=True)

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    async def _failing_context(**_kwargs):
        raise RuntimeError("lookup failed")

    async def _fake_run_agent_turn(**_kwargs):
        return "arsenal", "VERDICT: APPROVED"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "retrieve_arena_context_lines", _failing_context)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)
    assert session.items


@pytest.mark.asyncio
async def test_arena_mode_preserves_supermemory_context_after_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    session = _DummySession()
    ctx = _ctx(supermemory_enabled=True, rounds=2)

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    async def _fake_retrieve_context(**_kwargs):
        return ["Known incident from yesterday."]

    round_counter = 0

    async def _fake_run_agent_turn(**kwargs):
        nonlocal round_counter
        prompt = str(kwargs["prompt"])
        prompts.append(prompt)

        if kwargs.get("is_reviewer"):
            round_counter += 1
            verdict = "REVISE" if round_counter == 1 else "APPROVED"
            long_body = "x" * 4500
            return "arsenal", f"{long_body}\nVERDICT: {verdict}"

        return "arsenal", "final output"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "retrieve_arena_context_lines", _fake_retrieve_context)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)

    final_prompt = prompts[-1]
    assert "Supermemory context:" in final_prompt
    assert "- Known incident from yesterday." in final_prompt
