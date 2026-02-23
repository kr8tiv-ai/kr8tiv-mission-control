from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import task_mode_execution
from app.services.task_mode_execution import _ModeExecutionContext, _extract_verdict


def test_extract_verdict_accepts_approved() -> None:
    text = "Reviewer notes...\nVERDICT: APPROVED"
    assert _extract_verdict(text) == "APPROVED"


def test_extract_verdict_accepts_revise_case_insensitive() -> None:
    text = "something\nverdict: revise"
    assert _extract_verdict(text) == "REVISE"


def test_extract_verdict_returns_none_when_missing() -> None:
    assert _extract_verdict("No verdict provided") is None


@pytest.mark.asyncio
async def test_run_agent_turn_raises_when_board_agent_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _missing_board_agent(_board_id, _agent_id):
        return None

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _missing_board_agent)
    ctx = _ModeExecutionContext(
        board=SimpleNamespace(id=uuid4()),
        task=SimpleNamespace(id=uuid4()),
        gateway_config=None,
        allowed_agents=("arsenal",),
        reviewer_agent="arsenal",
    )
    with pytest.raises(RuntimeError, match="missing board agent"):
        await task_mode_execution._run_agent_turn(
            ctx=ctx,
            agent_id="arsenal",
            prompt="test prompt",
            round_number=1,
            max_rounds=3,
            is_reviewer=True,
        )


@pytest.mark.asyncio
async def test_run_agent_turn_raises_when_board_agent_session_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _board_agent_without_session(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id=None)

    monkeypatch.setattr(
        task_mode_execution,
        "_find_board_agent",
        _board_agent_without_session,
    )
    ctx = _ModeExecutionContext(
        board=SimpleNamespace(id=uuid4()),
        task=SimpleNamespace(id=uuid4()),
        gateway_config=object(),
        allowed_agents=("arsenal",),
        reviewer_agent="arsenal",
    )
    with pytest.raises(RuntimeError, match="missing session"):
        await task_mode_execution._run_agent_turn(
            ctx=ctx,
            agent_id="arsenal",
            prompt="test prompt",
            round_number=1,
            max_rounds=3,
            is_reviewer=False,
        )


@pytest.mark.asyncio
async def test_run_agent_turn_raises_when_gateway_returns_no_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _board_agent(_board_id, _agent_id):
        return SimpleNamespace(name="arsenal", openclaw_session_id="session-1")

    async def _noop_send_message(*_args, **_kwargs):
        return None

    async def _empty_history(*_args, **_kwargs):
        return {"messages": []}

    monkeypatch.setattr(task_mode_execution, "_find_board_agent", _board_agent)
    monkeypatch.setattr("app.services.openclaw.gateway_rpc.send_message", _noop_send_message)
    monkeypatch.setattr(task_mode_execution, "get_chat_history", _empty_history)
    ctx = _ModeExecutionContext(
        board=SimpleNamespace(id=uuid4()),
        task=SimpleNamespace(id=uuid4()),
        gateway_config=object(),
        allowed_agents=("arsenal",),
        reviewer_agent="arsenal",
    )
    with pytest.raises(RuntimeError, match="gateway response unavailable"):
        await task_mode_execution._run_agent_turn(
            ctx=ctx,
            agent_id="arsenal",
            prompt="test prompt",
            round_number=1,
            max_rounds=3,
            is_reviewer=False,
        )
