# ruff: noqa: S101
from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.agent_continuity import router as continuity_router
from app.api.deps import get_board_for_actor_read
from app.core.time import utcnow
from app.db.session import get_session
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.services.agent_continuity import AgentContinuityService


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(continuity_router)
    app.include_router(api_v1)
    return app


async def _create_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)


def _seed_board_rows(*, now_offset: timedelta = timedelta(0)) -> tuple[Organization, Gateway, Board]:
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
        name="Mission Control",
        slug="mission-control",
        gateway_id=gateway.id,
        created_at=utcnow() - now_offset,
        updated_at=utcnow() - now_offset,
    )
    return org, gateway, board


def _make_agent(
    *,
    board: Board,
    gateway: Gateway,
    name: str,
    session_key: str,
    minutes_ago: int,
) -> Agent:
    now = utcnow()
    return Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=gateway.id,
        name=name,
        status="online",
        openclaw_session_id=session_key,
        last_seen_at=now - timedelta(minutes=minutes_ago),
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_continuity_snapshot_identifies_alive_stale_and_unreachable_agents() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    org, gateway, board = _seed_board_rows()
    alive = _make_agent(
        board=board,
        gateway=gateway,
        name="alive-agent",
        session_key="session-alive",
        minutes_ago=1,
    )
    stale = _make_agent(
        board=board,
        gateway=gateway,
        name="stale-agent",
        session_key="session-stale",
        minutes_ago=25,
    )
    unreachable = _make_agent(
        board=board,
        gateway=gateway,
        name="unreachable-agent",
        session_key="session-missing",
        minutes_ago=1,
    )

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(alive)
        session.add(stale)
        session.add(unreachable)
        await session.commit()

    async def _fetch_runtime_sessions(_gateway: Gateway) -> set[str]:
        return {"session-alive", "session-stale"}

    async with session_maker() as session:
        service = AgentContinuityService(
            session=session,
            runtime_session_keys_fetcher=_fetch_runtime_sessions,
        )
        report = await service.snapshot_for_board(board_id=board.id)

    assert report.board_id == board.id
    assert report.counts["alive"] == 1
    assert report.counts["stale"] == 1
    assert report.counts["unreachable"] == 1
    by_name = {item.agent_name: item for item in report.agents}
    assert by_name["alive-agent"].continuity == "alive"
    assert by_name["stale-agent"].continuity == "stale"
    assert by_name["unreachable-agent"].continuity == "unreachable"
    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_continuity_api_returns_board_scoped_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org, gateway, board = _seed_board_rows(now_offset=timedelta(minutes=1))
    alive = _make_agent(
        board=board,
        gateway=gateway,
        name="alive-api-agent",
        session_key="session-alive-api",
        minutes_ago=1,
    )
    stale = _make_agent(
        board=board,
        gateway=gateway,
        name="stale-api-agent",
        session_key="session-stale-api",
        minutes_ago=22,
    )

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(alive)
        session.add(stale)
        await session.commit()

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_board_access(board_id: str) -> Board:
        assert UUID(board_id) == board.id
        return board

    async def _fake_fetch_runtime_sessions(self: AgentContinuityService, gateway_row: Gateway) -> set[str]:
        assert gateway_row.id == gateway.id
        return {"session-alive-api", "session-stale-api"}

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_board_for_actor_read] = _override_board_access
    monkeypatch.setattr(
        AgentContinuityService,
        "fetch_runtime_session_keys",
        _fake_fetch_runtime_sessions,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/api/v1/boards/{board.id}/agent-continuity")

    assert response.status_code == 200
    body = response.json()
    assert body["board_id"] == str(board.id)
    assert body["counts"]["alive"] == 1
    assert body["counts"]["stale"] == 1
    assert body["counts"]["unreachable"] == 0
    await engine.dispose()
