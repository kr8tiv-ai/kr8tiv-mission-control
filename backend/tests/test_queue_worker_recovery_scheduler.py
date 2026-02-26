# ruff: noqa: S101
from __future__ import annotations

import pytest

from app.services import queue_worker


class _SessionContext:
    def __init__(self) -> None:
        self.session = object()

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_run_recovery_scheduler_once_executes_sweep_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"run_once": 0}

    class _SchedulerStub:
        def __init__(self, *, session) -> None:
            self.session = session

        async def run_once(self):
            called["run_once"] += 1
            return type(
                "_Result",
                (),
                {
                    "board_count": 1,
                    "incident_count": 1,
                    "alerts_sent": 1,
                    "alerts_suppressed_dedupe": 0,
                    "alerts_skipped_status": 0,
                },
            )()

    monkeypatch.setattr(queue_worker.settings, "recovery_loop_enabled", True)
    monkeypatch.setattr(queue_worker, "RecoveryScheduler", _SchedulerStub)
    monkeypatch.setattr(queue_worker, "async_session_maker", lambda: _SessionContext())

    executed = await queue_worker.run_recovery_scheduler_once()

    assert executed is True
    assert called["run_once"] == 1


@pytest.mark.asyncio
async def test_run_recovery_scheduler_once_is_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(queue_worker.settings, "recovery_loop_enabled", False)

    class _SchedulerStub:
        def __init__(self, *, session) -> None:
            raise AssertionError("scheduler should not be instantiated when loop is disabled")

    monkeypatch.setattr(queue_worker, "RecoveryScheduler", _SchedulerStub)

    executed = await queue_worker.run_recovery_scheduler_once()

    assert executed is False
