# ruff: noqa: S101
from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.recovery_incidents import RecoveryIncident
from app.models.recovery_policies import RecoveryPolicy
from app.services.runtime.recovery_alerts import RecoveryAlertResult
from app.services.runtime.recovery_scheduler import RecoveryScheduler


async def _create_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)


def _seed_board_rows() -> tuple[Organization, Gateway, Board, Agent]:
    now = utcnow()
    org = Organization(id=uuid4(), name="KR8TIV")
    gateway = Gateway(
        id=uuid4(),
        organization_id=org.id,
        name="main-gateway",
        url="http://gateway.internal",
        token=None,
        workspace_root="/srv/openclaw",
    )
    board = Board(
        id=uuid4(),
        organization_id=org.id,
        gateway_id=gateway.id,
        name="Mission Control",
        slug="mission-control",
        created_at=now,
        updated_at=now,
    )
    agent = Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=gateway.id,
        name="friday",
        status="online",
        openclaw_session_id="agent:friday:main",
        last_seen_at=now - timedelta(minutes=20),
        created_at=now,
        updated_at=now,
    )
    return org, gateway, board, agent


class _EngineStub:
    def __init__(self, incidents: list[RecoveryIncident]) -> None:
        self.incidents = incidents
        self.calls: list[UUID] = []

    async def evaluate_board(self, *, board_id: UUID) -> list[RecoveryIncident]:
        self.calls.append(board_id)
        return list(self.incidents)


class _AlertSink:
    def __init__(self) -> None:
        self.calls: list[UUID] = []

    async def route_incident_alert(self, *, incident: RecoveryIncident, policy: RecoveryPolicy) -> RecoveryAlertResult:
        del policy
        self.calls.append(incident.id)
        return RecoveryAlertResult(
            channel="ui",
            delivered=True,
            attempted_channels=["ui"],
            message="ok",
        )


@pytest.mark.asyncio
async def test_scheduler_runs_recovery_for_board_and_routes_alerts() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    org, gateway, board, agent = _seed_board_rows()
    now = utcnow()
    incident = RecoveryIncident(
        organization_id=org.id,
        board_id=board.id,
        agent_id=agent.id,
        status="failed",
        reason="runtime_session_unreachable",
        action="session_resync",
        attempts=1,
        detected_at=now,
        created_at=now,
        updated_at=now,
    )
    engine_stub = _EngineStub([incident])
    alert_sink = _AlertSink()

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        session.add(RecoveryPolicy(organization_id=org.id, alert_dedupe_seconds=900))
        await session.commit()

        scheduler = RecoveryScheduler(
            session=session,
            recovery_engine_factory=lambda _: engine_stub,
            alert_service=alert_sink,
        )
        result = await scheduler.run_once()

        assert engine_stub.calls == [board.id]
        assert result.board_count == 1
        assert result.incident_count == 1
        assert result.alerts_sent == 1
        assert result.alerts_suppressed_dedupe == 0
        assert result.alerts_skipped_status == 0
        assert len(alert_sink.calls) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_scheduler_suppresses_duplicate_alerts_within_dedupe_window() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    org, gateway, board, agent = _seed_board_rows()
    now = utcnow()
    existing = RecoveryIncident(
        organization_id=org.id,
        board_id=board.id,
        agent_id=agent.id,
        status="failed",
        reason="runtime_session_unreachable",
        action="session_resync",
        attempts=1,
        detected_at=now - timedelta(seconds=120),
        created_at=now - timedelta(seconds=120),
        updated_at=now - timedelta(seconds=120),
    )
    incoming = RecoveryIncident(
        organization_id=org.id,
        board_id=board.id,
        agent_id=agent.id,
        status="failed",
        reason="runtime_session_unreachable",
        action="session_resync",
        attempts=2,
        detected_at=now,
        created_at=now,
        updated_at=now,
    )
    engine_stub = _EngineStub([incoming])
    alert_sink = _AlertSink()

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        session.add(RecoveryPolicy(organization_id=org.id, alert_dedupe_seconds=900))
        session.add(existing)
        await session.commit()

        scheduler = RecoveryScheduler(
            session=session,
            recovery_engine_factory=lambda _: engine_stub,
            alert_service=alert_sink,
        )
        result = await scheduler.run_once()

        assert result.board_count == 1
        assert result.incident_count == 1
        assert result.alerts_sent == 0
        assert result.alerts_suppressed_dedupe == 1
        assert len(alert_sink.calls) == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_scheduler_ignores_suppressed_incident_status_for_alert_delivery() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    org, gateway, board, agent = _seed_board_rows()
    now = utcnow()
    incident = RecoveryIncident(
        organization_id=org.id,
        board_id=board.id,
        agent_id=agent.id,
        status="suppressed",
        reason="cooldown_active",
        action=None,
        attempts=2,
        detected_at=now,
        created_at=now,
        updated_at=now,
    )
    engine_stub = _EngineStub([incident])
    alert_sink = _AlertSink()

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        session.add(RecoveryPolicy(organization_id=org.id, alert_dedupe_seconds=900))
        await session.commit()

        scheduler = RecoveryScheduler(
            session=session,
            recovery_engine_factory=lambda _: engine_stub,
            alert_service=alert_sink,
        )
        result = await scheduler.run_once()

        assert result.board_count == 1
        assert result.incident_count == 1
        assert result.alerts_sent == 0
        assert result.alerts_skipped_status == 1
        assert result.alerts_suppressed_dedupe == 0
        assert len(alert_sink.calls) == 0
    await engine.dispose()
