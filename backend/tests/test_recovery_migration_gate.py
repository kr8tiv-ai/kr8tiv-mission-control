# ruff: noqa: S101
from __future__ import annotations

import pytest

from app.services.runtime import migration_gate


@pytest.mark.asyncio
async def test_gate_ready_when_db_revision_matches_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_gate.reset_scheduler_migration_gate()

    monkeypatch.setattr(migration_gate, "get_alembic_head_revision", lambda: "abc123")

    async def _current_revision() -> str | None:
        return "abc123"

    monkeypatch.setattr(migration_gate, "_fetch_current_migration_revision", _current_revision)

    ready = await migration_gate.is_scheduler_migration_ready()

    assert ready is True


@pytest.mark.asyncio
async def test_gate_not_ready_when_revision_differs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_gate.reset_scheduler_migration_gate()

    monkeypatch.setattr(migration_gate, "get_alembic_head_revision", lambda: "abc123")

    async def _current_revision() -> str | None:
        return "def999"

    monkeypatch.setattr(migration_gate, "_fetch_current_migration_revision", _current_revision)

    ready = await migration_gate.is_scheduler_migration_ready()

    assert ready is False


@pytest.mark.asyncio
async def test_gate_caches_successful_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_gate.reset_scheduler_migration_gate()
    calls = {"fetch": 0}

    monkeypatch.setattr(migration_gate, "get_alembic_head_revision", lambda: "abc123")

    async def _current_revision() -> str | None:
        calls["fetch"] += 1
        return "abc123"

    monkeypatch.setattr(migration_gate, "_fetch_current_migration_revision", _current_revision)

    first = await migration_gate.is_scheduler_migration_ready()
    second = await migration_gate.is_scheduler_migration_ready()

    assert first is True
    assert second is True
    assert calls["fetch"] == 1
