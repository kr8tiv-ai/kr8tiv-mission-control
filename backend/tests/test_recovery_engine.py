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
from app.services.agent_continuity import AgentContinuityItem, AgentContinuityReport
from app.services.runtime.recovery_engine import RecoveryEngine


async def _create_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)


def _seed_board_rows() -> tuple[Organization, Gateway, Board]:
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
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    return org, gateway, board


def _make_agent(*, board: Board, gateway: Gateway, name: str, session_key: str) -> Agent:
    now = utcnow()
    return Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=gateway.id,
        name=name,
        status="online",
        openclaw_session_id=session_key,
        last_seen_at=now - timedelta(minutes=20),
        created_at=now,
        updated_at=now,
    )


def _report_for(agent: Agent, *, continuity: str, reason: str) -> AgentContinuityReport:
    return AgentContinuityReport(
        board_id=agent.board_id or uuid4(),
        generated_at=utcnow(),
        runtime_error=None,
        counts={"alive": 0, "stale": 1 if continuity == "stale" else 0, "unreachable": 1 if continuity == "unreachable" else 0},
        agents=[
            AgentContinuityItem(
                agent_id=agent.id,
                agent_name=agent.name,
                board_id=agent.board_id,
                status=agent.status,
                continuity=continuity,  # type: ignore[arg-type]
                continuity_reason=reason,
                runtime_session_id=agent.openclaw_session_id,
                runtime_reachable=continuity != "unreachable",
                last_seen_at=agent.last_seen_at,
                heartbeat_age_seconds=1200,
            )
        ],
    )


@pytest.mark.asyncio
async def test_recovery_engine_detects_stale_and_queues_recovery() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org, gateway, board = _seed_board_rows()
    agent = _make_agent(board=board, gateway=gateway, name="edith", session_key="agent:edith:main")
    report = _report_for(agent, continuity="stale", reason="heartbeat_stale")

    action_calls: list[UUID] = []

    async def _recover(*, board_id: UUID, agent_id: UUID, continuity_reason: str) -> tuple[bool, str]:
        assert board_id == board.id
        assert continuity_reason == "heartbeat_stale"
        action_calls.append(agent_id)
        return True, "heartbeat_resync"

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        session.add(RecoveryPolicy(organization_id=org.id))
        await session.commit()

        engine_service = RecoveryEngine(
            session=session,
            continuity_snapshot_fetcher=lambda *, board_id: report,
            recovery_action=_recover,
        )
        incidents = await engine_service.evaluate_board(board_id=board.id)

        assert len(incidents) == 1
        assert incidents[0].status == "recovered"
        assert incidents[0].action == "heartbeat_resync"
        assert incidents[0].attempts == 1
        assert action_calls == [agent.id]
    await engine.dispose()


@pytest.mark.asyncio
async def test_recovery_engine_respects_cooldown_and_attempt_limits() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org, gateway, board = _seed_board_rows()
    agent = _make_agent(board=board, gateway=gateway, name="friday", session_key="agent:friday:main")
    report = _report_for(agent, continuity="unreachable", reason="runtime_session_unreachable")

    async with session_maker() as session:
        now = utcnow()
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        session.add(
            RecoveryPolicy(
                organization_id=org.id,
                cooldown_seconds=300,
                max_restarts_per_hour=1,
            )
        )
        session.add(
            RecoveryIncident(
                organization_id=org.id,
                board_id=board.id,
                agent_id=agent.id,
                status="recovered",
                reason="runtime_session_unreachable",
                action="session_resync",
                attempts=1,
                detected_at=now - timedelta(seconds=30),
                recovered_at=now - timedelta(seconds=20),
                created_at=now - timedelta(seconds=30),
                updated_at=now - timedelta(seconds=20),
            )
        )
        await session.commit()

        async def _should_not_run(**_: object) -> tuple[bool, str]:
            raise AssertionError("recovery action should not be invoked while in cooldown")

        engine_service = RecoveryEngine(
            session=session,
            continuity_snapshot_fetcher=lambda *, board_id: report,
            recovery_action=_should_not_run,
        )
        incidents = await engine_service.evaluate_board(board_id=board.id)

        assert len(incidents) == 1
        assert incidents[0].status == "suppressed"
        assert incidents[0].reason == "cooldown_active"
    await engine.dispose()


@pytest.mark.asyncio
async def test_recovery_engine_marks_failed_when_gateway_recovery_errors() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org, gateway, board = _seed_board_rows()
    agent = _make_agent(board=board, gateway=gateway, name="arsenal", session_key="agent:arsenal:main")
    report = _report_for(agent, continuity="stale", reason="heartbeat_stale")

    async def _failing_recover(**_: object) -> tuple[bool, str]:
        raise RuntimeError("gateway down")

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        session.add(RecoveryPolicy(organization_id=org.id))
        await session.commit()

        engine_service = RecoveryEngine(
            session=session,
            continuity_snapshot_fetcher=lambda *, board_id: report,
            recovery_action=_failing_recover,
        )
        incidents = await engine_service.evaluate_board(board_id=board.id)

        assert len(incidents) == 1
        assert incidents[0].status == "failed"
        assert "gateway down" in (incidents[0].last_error or "")
    await engine.dispose()


@pytest.mark.asyncio
async def test_recovery_engine_force_bypasses_cooldown_and_resyncs_heartbeat() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org, gateway, board = _seed_board_rows()
    agent = _make_agent(board=board, gateway=gateway, name="jocasta", session_key="agent:jocasta:main")
    report = _report_for(agent, continuity="stale", reason="heartbeat_stale")

    async with session_maker() as session:
        now = utcnow()
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        session.add(RecoveryPolicy(organization_id=org.id, cooldown_seconds=300))
        session.add(
            RecoveryIncident(
                organization_id=org.id,
                board_id=board.id,
                agent_id=agent.id,
                status="recovered",
                reason="heartbeat_stale",
                action="session_resync",
                attempts=1,
                detected_at=now - timedelta(seconds=15),
                recovered_at=now - timedelta(seconds=15),
                created_at=now - timedelta(seconds=15),
                updated_at=now - timedelta(seconds=15),
            )
        )
        await session.commit()

        engine_service = RecoveryEngine(
            session=session,
            continuity_snapshot_fetcher=lambda *, board_id: report,
            force_heartbeat_resync=True,
        )
        incidents = await engine_service.evaluate_board(
            board_id=board.id,
            bypass_cooldown=True,
        )

        assert len(incidents) == 1
        assert incidents[0].status == "recovered"
        assert incidents[0].action == "forced_heartbeat_resync"

        persisted_agent = await Agent.objects.by_id(agent.id).first(session)
        assert persisted_agent is not None
        assert persisted_agent.status == "online"
        assert persisted_agent.last_seen_at is not None
        assert (utcnow() - persisted_agent.last_seen_at).total_seconds() < 10
    await engine.dispose()
