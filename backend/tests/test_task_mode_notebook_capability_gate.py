from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import task_mode_execution
from app.services.notebooklm_adapter import NotebookLMError
from app.services.notebooklm_capability_gate import NotebookCapabilityGateResult
from app.services.task_mode_execution import _ModeExecutionContext


class _DummySession:
    def __init__(self) -> None:
        self.items: list[object] = []

    def add(self, item: object) -> None:
        self.items.append(item)


def _gate_result(state: str, reason: str = "x") -> NotebookCapabilityGateResult:
    return NotebookCapabilityGateResult(
        state=state,  # type: ignore[arg-type]
        reason=reason,
        operator_message=f"Gate {state}",
        checked_at=datetime.utcnow(),
        selected_profile=None,
        notebook_count=None,
    )


@pytest.mark.asyncio
async def test_notebook_mode_blocks_when_capability_gate_misconfig(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _DummySession()
    task = SimpleNamespace(
        id=uuid4(),
        title="Notebook task",
        description="Need notebook answer",
        arena_config={},
        task_mode="notebook",
        notebook_id="notebook-1",
        notebook_share_url=None,
        notebook_profile="auto",
    )
    ctx = _ModeExecutionContext(
        board=SimpleNamespace(id=uuid4()),
        task=task,
        gateway_config=None,
        allowed_agents=("arsenal",),
        reviewer_agent="arsenal",
    )

    async def _fake_gate(**_kwargs):
        return _gate_result("misconfig", "invalid_profile")

    async def _should_not_run(**_kwargs):
        raise AssertionError("Notebook operations should be blocked by capability gate")

    monkeypatch.setattr(task_mode_execution, "evaluate_notebooklm_capability", _fake_gate)
    monkeypatch.setattr(task_mode_execution, "query_notebook", _should_not_run)

    with pytest.raises(NotebookLMError, match="NotebookLM Gate"):
        await task_mode_execution._execute_notebook_mode(session, ctx)


@pytest.mark.asyncio
async def test_notebook_creation_mode_blocks_when_capability_gate_hard_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SimpleNamespace(
        id=uuid4(),
        title="Notebook creation task",
        description="Build notebook",
        arena_config={"sources": {"urls": ["https://example.com"], "texts": []}},
        task_mode="notebook_creation",
        notebook_id="",
        notebook_share_url=None,
        notebook_profile="auto",
    )
    ctx = _ModeExecutionContext(
        board=SimpleNamespace(id=uuid4()),
        task=task,
        gateway_config=None,
        allowed_agents=("arsenal",),
        reviewer_agent="arsenal",
    )

    async def _fake_gate(**_kwargs):
        return _gate_result("hard_fail", "forbidden")

    async def _should_not_run(**_kwargs):
        raise AssertionError("Notebook operations should be blocked by capability gate")

    monkeypatch.setattr(task_mode_execution, "evaluate_notebooklm_capability", _fake_gate)
    monkeypatch.setattr(task_mode_execution, "create_notebook", _should_not_run)

    with pytest.raises(NotebookLMError, match="NotebookLM Gate"):
        await task_mode_execution._execute_notebook_creation_mode(ctx)

