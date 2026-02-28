"""Guardrails for suppressing heartbeat storms from misbehaving agents."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.config import settings

T = TypeVar("T")


class AgentHeartbeatGuard:
    """Applies singleflight + cadence throttling to heartbeat updates."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_emit_at: dict[str, float] = {}

    def _lock_for(self, agent_id: str) -> asyncio.Lock:
        lock = self._locks.get(agent_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[agent_id] = lock
        return lock

    def _should_emit(self, *, agent_id: str) -> bool:
        min_interval = max(0, int(settings.heartbeat_min_interval_seconds))
        if min_interval <= 0:
            return True
        now = time.monotonic()
        last_emit = self._last_emit_at.get(agent_id)
        if last_emit is None:
            return True
        return (now - last_emit) >= min_interval

    async def _maybe_jitter(self) -> None:
        jitter_seconds = max(0, int(settings.heartbeat_jitter_seconds))
        if jitter_seconds <= 0:
            return
        await asyncio.sleep(random.uniform(0.0, float(jitter_seconds)))

    async def execute(
        self,
        *,
        agent_id: str,
        emit: Callable[[], Awaitable[T]],
        on_skip: Callable[[], T],
    ) -> T:
        """Emit heartbeat if cadence allows, otherwise return fallback state."""
        if settings.heartbeat_singleflight_enabled:
            async with self._lock_for(agent_id):
                if not self._should_emit(agent_id=agent_id):
                    return on_skip()
                await self._maybe_jitter()
                result = await emit()
                self._last_emit_at[agent_id] = time.monotonic()
                return result

        if not self._should_emit(agent_id=agent_id):
            return on_skip()
        await self._maybe_jitter()
        result = await emit()
        self._last_emit_at[agent_id] = time.monotonic()
        return result


_HEARTBEAT_GUARD = AgentHeartbeatGuard()


def get_heartbeat_guard() -> AgentHeartbeatGuard:
    """Return process-scoped heartbeat guard singleton."""
    return _HEARTBEAT_GUARD

