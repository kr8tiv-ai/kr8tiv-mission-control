# ruff: noqa: S101
from __future__ import annotations

import asyncio

import pytest

from app.services import agent_heartbeat_guard


@pytest.mark.asyncio
async def test_heartbeat_guard_skips_emit_inside_min_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_heartbeat_guard.settings, "heartbeat_min_interval_seconds", 60)
    monkeypatch.setattr(agent_heartbeat_guard.settings, "heartbeat_jitter_seconds", 0)
    monkeypatch.setattr(agent_heartbeat_guard.settings, "heartbeat_singleflight_enabled", True)

    guard = agent_heartbeat_guard.AgentHeartbeatGuard()
    calls = {"emit": 0, "skip": 0}

    async def _emit() -> str:
        calls["emit"] += 1
        return "emitted"

    def _skip() -> str:
        calls["skip"] += 1
        return "skipped"

    first = await guard.execute(agent_id="a1", emit=_emit, on_skip=_skip)
    second = await guard.execute(agent_id="a1", emit=_emit, on_skip=_skip)

    assert first == "emitted"
    assert second == "skipped"
    assert calls["emit"] == 1
    assert calls["skip"] == 1


@pytest.mark.asyncio
async def test_heartbeat_guard_singleflight_allows_only_one_emit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_heartbeat_guard.settings, "heartbeat_min_interval_seconds", 999)
    monkeypatch.setattr(agent_heartbeat_guard.settings, "heartbeat_jitter_seconds", 0)
    monkeypatch.setattr(agent_heartbeat_guard.settings, "heartbeat_singleflight_enabled", True)

    guard = agent_heartbeat_guard.AgentHeartbeatGuard()
    calls = {"emit": 0, "skip": 0}
    gate = asyncio.Event()

    async def _emit() -> str:
        calls["emit"] += 1
        if calls["emit"] == 1:
            gate.set()
            await asyncio.sleep(0.05)
        return "emitted"

    def _skip() -> str:
        calls["skip"] += 1
        return "skipped"

    first_task = asyncio.create_task(guard.execute(agent_id="a2", emit=_emit, on_skip=_skip))
    await gate.wait()
    second_task = asyncio.create_task(guard.execute(agent_id="a2", emit=_emit, on_skip=_skip))

    first = await first_task
    second = await second_task

    assert first == "emitted"
    assert second == "skipped"
    assert calls["emit"] == 1
    assert calls["skip"] == 1

