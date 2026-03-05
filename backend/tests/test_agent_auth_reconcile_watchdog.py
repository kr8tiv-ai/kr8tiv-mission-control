# ruff: noqa: S101
from __future__ import annotations

import app.services.openclaw.auth_reconcile_watchdog as auth_reconcile_watchdog


def test_record_401_failure_ignores_non_agent_path(monkeypatch) -> None:
    auth_reconcile_watchdog.reset_state_for_tests()
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_on_401_enabled",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_401_threshold",
        2,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_401_window_seconds",
        60,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_cooldown_seconds",
        120,
        raising=False,
    )

    scheduled: list[object] = []

    def _schedule(coro: object) -> None:
        scheduled.append(coro)
        close = getattr(coro, "close", None)
        if callable(close):
            close()

    monkeypatch.setattr(auth_reconcile_watchdog, "_schedule_reconcile_task", _schedule)

    auth_reconcile_watchdog.record_401_failure(path="/api/v1/runtime/ops")
    auth_reconcile_watchdog.record_401_failure(path="/api/v1/runtime/ops")

    assert scheduled == []


def test_record_401_failure_triggers_reconcile_after_threshold(monkeypatch) -> None:
    auth_reconcile_watchdog.reset_state_for_tests()
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_on_401_enabled",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_401_threshold",
        2,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_401_window_seconds",
        60,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_cooldown_seconds",
        120,
        raising=False,
    )

    ticks = iter([100.0, 101.0, 102.0])
    monkeypatch.setattr(auth_reconcile_watchdog, "_now_monotonic", lambda: next(ticks))

    scheduled: list[object] = []

    def _schedule(coro: object) -> None:
        scheduled.append(coro)
        close = getattr(coro, "close", None)
        if callable(close):
            close()

    monkeypatch.setattr(auth_reconcile_watchdog, "_schedule_reconcile_task", _schedule)

    auth_reconcile_watchdog.record_401_failure(path="/api/v1/agent/boards")
    assert scheduled == []

    auth_reconcile_watchdog.record_401_failure(path="/api/v1/agent/boards")
    assert len(scheduled) == 1


def test_record_401_failure_respects_cooldown(monkeypatch) -> None:
    auth_reconcile_watchdog.reset_state_for_tests()
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_on_401_enabled",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_401_threshold",
        2,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_401_window_seconds",
        60,
        raising=False,
    )
    monkeypatch.setattr(
        auth_reconcile_watchdog.settings,
        "auth_reconcile_cooldown_seconds",
        300,
        raising=False,
    )

    ticks = iter([10.0, 11.0, 12.0, 15.0, 16.0, 17.0])
    monkeypatch.setattr(auth_reconcile_watchdog, "_now_monotonic", lambda: next(ticks))

    scheduled: list[object] = []

    def _schedule(coro: object) -> None:
        scheduled.append(coro)
        close = getattr(coro, "close", None)
        if callable(close):
            close()

    monkeypatch.setattr(auth_reconcile_watchdog, "_schedule_reconcile_task", _schedule)

    auth_reconcile_watchdog.record_401_failure(path="/api/v1/agent/boards")
    auth_reconcile_watchdog.record_401_failure(path="/api/v1/agent/boards")
    assert len(scheduled) == 1

    # Within cooldown window; should not schedule again.
    auth_reconcile_watchdog.record_401_failure(path="/api/v1/agent/boards")
    auth_reconcile_watchdog.record_401_failure(path="/api/v1/agent/boards")
    assert len(scheduled) == 1
