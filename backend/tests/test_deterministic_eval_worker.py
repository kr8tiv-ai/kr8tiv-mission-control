from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.deterministic_evals import DeterministicEval
from app.models.organizations import Organization
from app.models.run_telemetry import RunTelemetry
from app.services import deterministic_eval_execution
from app.services.queue import QueuedTask


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


@pytest.mark.asyncio
async def test_deterministic_eval_worker_flags_missing_engineering_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(deterministic_eval_execution, "async_session_maker", session_maker)

    try:
        async with session_maker() as session:
            org = Organization(id=uuid4(), name="org")
            session.add(org)
            run = RunTelemetry(
                id=uuid4(),
                organization_id=org.id,
                pack_key="engineering-delivery-pack",
                tier="personal",
                success_bool=True,
                retries=0,
                latency_ms=120,
                format_contract_passed=True,
                approval_gate_passed=True,
                checks={
                    "pr_created": True,
                    "ci_passed": True,
                    "human_reviewed": False,
                },
                run_metadata={"lane": "engineering_swarm"},
            )
            session.add(run)
            await session.commit()

        task = QueuedTask(
            task_type="deterministic_eval",
            payload={"run_telemetry_id": str(run.id), "queued_at": datetime.now(UTC).isoformat()},
            created_at=datetime.now(UTC),
            attempts=0,
        )
        await deterministic_eval_execution.execute_deterministic_eval(task)

        async with session_maker() as session:
            row = (
                await session.exec(
                    select(DeterministicEval).where(col(DeterministicEval.run_telemetry_id) == run.id)
                )
            ).first()
            assert row is not None
            assert row.approval_gate_compliance is False
            assert row.hard_regression is True
            assert row.details.get("missing_checks") == ["human_reviewed"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_deterministic_eval_worker_scores_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(deterministic_eval_execution, "async_session_maker", session_maker)

    try:
        async with session_maker() as session:
            org = Organization(id=uuid4(), name="org")
            session.add(org)
            baseline = RunTelemetry(
                id=uuid4(),
                organization_id=org.id,
                pack_key="engineering-delivery-pack",
                tier="personal",
                success_bool=True,
                retries=0,
                latency_ms=200,
                format_contract_passed=True,
                approval_gate_passed=True,
                checks={
                    "pr_created": True,
                    "ci_passed": True,
                    "human_reviewed": True,
                },
                run_metadata={"lane": "engineering_swarm"},
            )
            target = RunTelemetry(
                id=uuid4(),
                organization_id=org.id,
                pack_key="engineering-delivery-pack",
                tier="personal",
                success_bool=True,
                retries=0,
                latency_ms=120,
                format_contract_passed=True,
                approval_gate_passed=True,
                checks={
                    "pr_created": True,
                    "ci_passed": True,
                    "human_reviewed": True,
                },
                run_metadata={"lane": "engineering_swarm"},
            )
            session.add(baseline)
            session.add(target)
            await session.commit()

        task = QueuedTask(
            task_type="deterministic_eval",
            payload={"run_telemetry_id": str(target.id), "queued_at": datetime.now(UTC).isoformat()},
            created_at=datetime.now(UTC),
            attempts=0,
        )
        await deterministic_eval_execution.execute_deterministic_eval(task)

        async with session_maker() as session:
            row = (
                await session.exec(
                    select(DeterministicEval).where(col(DeterministicEval.run_telemetry_id) == target.id)
                )
            ).first()
            assert row is not None
            assert row.approval_gate_compliance is True
            assert row.hard_regression is False
            assert row.score >= 80
            assert row.latency_regression_pct < 0
    finally:
        await engine.dispose()
