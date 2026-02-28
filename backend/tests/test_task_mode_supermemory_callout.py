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


def _ctx(
    *,
    supermemory_enabled: bool,
    rounds: int = 1,
    gsd_spec_driven: bool = False,
    agents: list[str] | None = None,
    final_agent: str = "arsenal",
    allowed_agents: tuple[str, ...] = ("arsenal",),
    reviewer_agent: str = "arsenal",
) -> _ModeExecutionContext:
    selected_agents = agents or ["arsenal"]
    task = SimpleNamespace(
        id=uuid4(),
        title="Investigate issue",
        description="Need reliable fix path",
        arena_config={
            "agents": selected_agents,
            "rounds": rounds,
            "final_agent": final_agent,
            "supermemory_enabled": supermemory_enabled,
            "gsd_spec_driven": gsd_spec_driven,
        },
        task_mode="arena",
        notebook_profile="auto",
    )
    return _ModeExecutionContext(
        board=SimpleNamespace(id=uuid4()),
        task=task,
        gateway_config=object(),
        allowed_agents=allowed_agents,
        reviewer_agent=reviewer_agent,
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


@pytest.mark.asyncio
async def test_arena_mode_injects_gsd_spec_guidance_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    session = _DummySession()
    ctx = _ctx(supermemory_enabled=False, gsd_spec_driven=True)

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    async def _fake_run_agent_turn(**kwargs):
        prompt = str(kwargs["prompt"])
        prompts.append(prompt)
        if kwargs.get("is_reviewer"):
            return "arsenal", "Reviewer output\nVERDICT: APPROVED"
        return "arsenal", "final output"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)

    assert prompts
    assert all("GSD Spec-Driven Evaluation:" in prompt for prompt in prompts)
    assert all(
        "Map recommendation to stage gates: spec -> plan -> execute -> verify -> done."
        in prompt
        for prompt in prompts
    )


@pytest.mark.asyncio
async def test_arena_mode_reprompts_reviewer_when_verdict_missing_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    session = _DummySession()
    ctx = _ctx(supermemory_enabled=False, rounds=1)

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    reviewer_turn_count = 0

    async def _fake_run_agent_turn(**kwargs):
        nonlocal reviewer_turn_count
        prompt = str(kwargs["prompt"])
        prompts.append(prompt)
        if kwargs.get("is_reviewer"):
            reviewer_turn_count += 1
            if reviewer_turn_count == 1:
                return "arsenal", "I recommend revise due to risk."
            return "arsenal", "Follow-up review\nVERDICT: APPROVED"
        return "arsenal", "final output"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)

    assert reviewer_turn_count == 2
    assert any("STRICT VERDICT REQUIRED" in prompt for prompt in prompts)


@pytest.mark.asyncio
async def test_arena_mode_skips_non_reviewer_agent_failure_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _DummySession()
    ctx = _ctx(
        supermemory_enabled=False,
        rounds=1,
        agents=["edith", "arsenal"],
        final_agent="arsenal",
        allowed_agents=("edith", "arsenal"),
        reviewer_agent="arsenal",
    )

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name=_agent_id, openclaw_session_id=f"session-{_agent_id}")

    async def _fake_run_agent_turn(**kwargs):
        agent_id = str(kwargs["agent_id"])
        if agent_id == "edith":
            raise RuntimeError("Arena agent 'edith' unavailable: gateway response unavailable")
        if kwargs.get("is_reviewer"):
            return "arsenal", "review result\nVERDICT: APPROVED"
        return "arsenal", "final output"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)
    assert session.items


@pytest.mark.asyncio
async def test_arena_mode_forces_revise_when_reviewer_never_returns_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _DummySession()
    ctx = _ctx(
        supermemory_enabled=False,
        rounds=1,
        agents=["arsenal"],
        final_agent="arsenal",
        allowed_agents=("arsenal",),
        reviewer_agent="arsenal",
    )

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    reviewer_attempts = 0

    async def _fake_run_agent_turn(**kwargs):
        nonlocal reviewer_attempts
        if kwargs.get("is_reviewer"):
            reviewer_attempts += 1
            if reviewer_attempts == 1:
                return "arsenal", "review without strict verdict"
            return "arsenal", "still missing strict verdict"
        return "arsenal", "final output"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)

    task_iterations = [item for item in session.items if hasattr(item, "verdict")]
    assert task_iterations
    assert any(getattr(item, "verdict", None) == "REVISE" for item in task_iterations)


@pytest.mark.asyncio
async def test_arena_mode_degrades_when_final_agent_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _DummySession()
    ctx = _ctx(
        supermemory_enabled=False,
        rounds=1,
        agents=["arsenal"],
        final_agent="arsenal",
        allowed_agents=("arsenal",),
        reviewer_agent="arsenal",
    )

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    async def _fake_run_agent_turn(**kwargs):
        if kwargs.get("is_reviewer"):
            return "arsenal", "review result\nVERDICT: APPROVED"
        raise RuntimeError("Arena agent 'arsenal' unavailable: gateway response unavailable")

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)

    comments = [item for item in session.items if hasattr(item, "message")]
    assert comments
    assert any(
        "Arena degraded mode: final agent 'arsenal' unavailable" in str(getattr(item, "message", ""))
        for item in comments
    )


@pytest.mark.asyncio
async def test_arena_notebook_injects_notebook_context_and_persists_final_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    add_sources_calls: list[tuple[str, tuple[str, ...], str]] = []
    query_called = False
    session = _DummySession()
    ctx = _ctx(supermemory_enabled=False, rounds=1)
    ctx.task.task_mode = "arena_notebook"
    ctx.task.notebook_profile = "enterprise"

    async def _fake_find_board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    async def _fake_enforce_notebook(*_args, **_kwargs):
        return None

    async def _fake_ensure_notebook(_task):
        return SimpleNamespace(
            notebook_id="nb-123",
            share_url="https://notebook/share/nb-123",
            profile="enterprise",
        )

    async def _fake_query_notebook(**_kwargs):
        nonlocal query_called
        query_called = True
        return "Notebook baseline context"

    async def _fake_add_sources(*, notebook_id, sources, profile):
        add_sources_calls.append((str(notebook_id), tuple(sources.texts), str(profile)))

    async def _fake_run_agent_turn(**kwargs):
        assert query_called is True
        prompt = str(kwargs["prompt"])
        prompts.append(prompt)
        if kwargs.get("is_reviewer"):
            return "arsenal", "review output\nVERDICT: APPROVED"
        return "arsenal", "final synthesis"

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _fake_find_board_agent)
    monkeypatch.setattr(task_mode_execution, "_enforce_notebooklm_capability", _fake_enforce_notebook)
    monkeypatch.setattr(task_mode_execution, "_ensure_notebook_for_task", _fake_ensure_notebook)
    monkeypatch.setattr(task_mode_execution, "query_notebook", _fake_query_notebook)
    monkeypatch.setattr(task_mode_execution, "add_sources", _fake_add_sources)
    monkeypatch.setattr(task_mode_execution, "_run_agent_turn", _fake_run_agent_turn)

    await task_mode_execution._execute_arena_mode(session, ctx)

    assert prompts
    assert all("NotebookLM context:" in prompt for prompt in prompts)
    assert all("- Notebook baseline context" in prompt for prompt in prompts)
    assert add_sources_calls == [("nb-123", ("final synthesis",), "enterprise")]
