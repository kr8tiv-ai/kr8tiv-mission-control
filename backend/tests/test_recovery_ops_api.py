# ruff: noqa: S101
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.recovery_ops import router as recovery_ops_router
from app.core.time import utcnow
from app.db.session import get_session
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.recovery_incidents import RecoveryIncident
from app.services.organizations import OrganizationContext
from app.services.runtime.recovery_engine import RecoveryEngine


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(recovery_ops_router)
    app.include_router(api_v1)
    return app


async def _create_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)


def _org_context(org: Organization) -> OrganizationContext:
    from app.models.organization_members import OrganizationMember

    member = OrganizationMember(
        organization_id=org.id,
        user_id=uuid4(),
        role="owner",
        all_boards_read=True,
        all_boards_write=True,
    )
    return OrganizationContext(organization=org, member=member)


@pytest.mark.asyncio
async def test_get_recovery_policy_requires_admin() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _deny_org_admin() -> OrganizationContext:
        raise HTTPException(status_code=403, detail="forbidden")

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _deny_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/runtime/recovery/policy")

    assert response.status_code == 403
    await engine.dispose()


@pytest.mark.asyncio
async def test_update_recovery_policy_persists_limits() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")

    async with session_maker() as session:
        session.add(org)
        await session.commit()

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return _org_context(org)

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        updated = await client.put(
            "/api/v1/runtime/recovery/policy",
            json={
                "enabled": True,
                "stale_after_seconds": 600,
                "max_restarts_per_hour": 5,
                "cooldown_seconds": 120,
                "alert_dedupe_seconds": 600,
                "alert_telegram": True,
                "alert_whatsapp": False,
                "alert_ui": True,
            },
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["stale_after_seconds"] == 600
        assert body["max_restarts_per_hour"] == 5
        assert body["cooldown_seconds"] == 120
        assert body["alert_dedupe_seconds"] == 600
        assert body["alert_whatsapp"] is False

        fetched = await client.get("/api/v1/runtime/recovery/policy")
        assert fetched.status_code == 200
        assert fetched.json()["cooldown_seconds"] == 120
        assert fetched.json()["alert_dedupe_seconds"] == 600
    await engine.dispose()


@pytest.mark.asyncio
async def test_run_recovery_now_returns_incident_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")
    gateway = Gateway(
        id=uuid4(),
        organization_id=org.id,
        name="main-gateway",
        url="http://gateway.internal",
        token=None,
        workspace_root="/srv/openclaw",
    )
    board = Board(id=uuid4(), organization_id=org.id, name="MC", slug="mc", gateway_id=gateway.id)
    agent = Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=gateway.id,
        name="friday",
        status="online",
        openclaw_session_id="agent:friday:main",
        last_seen_at=utcnow() - timedelta(minutes=20),
    )

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        await session.commit()

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return _org_context(org)

    async def _fake_evaluate_board(
        self: RecoveryEngine,
        *,
        board_id,
        bypass_cooldown: bool = False,
    ):  # type: ignore[override]
        assert board_id == board.id
        assert bypass_cooldown is False
        now = utcnow()
        return [
            RecoveryIncident(
                organization_id=org.id,
                board_id=board.id,
                agent_id=agent.id,
                status="recovered",
                reason="heartbeat_stale",
                action="heartbeat_resync",
                attempts=1,
                detected_at=now,
                recovered_at=now,
                created_at=now,
                updated_at=now,
            )
        ]

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    monkeypatch.setattr(RecoveryEngine, "evaluate_board", _fake_evaluate_board)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(f"/api/v1/runtime/recovery/run?board_id={board.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["board_id"] == str(board.id)
    assert body["total_incidents"] == 1
    assert body["recovered"] == 1
    assert body["failed"] == 0
    assert body["suppressed"] == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_run_recovery_now_force_bypasses_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")
    gateway = Gateway(
        id=uuid4(),
        organization_id=org.id,
        name="main-gateway",
        url="http://gateway.internal",
        token=None,
        workspace_root="/srv/openclaw",
    )
    board = Board(id=uuid4(), organization_id=org.id, name="MC", slug="mc", gateway_id=gateway.id)
    agent = Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=gateway.id,
        name="edith",
        status="offline",
        openclaw_session_id="agent:edith:main",
        last_seen_at=utcnow() - timedelta(minutes=20),
    )

    async with session_maker() as session:
        session.add(org)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        await session.commit()

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return _org_context(org)

    seen: dict[str, bool] = {"bypass_cooldown": False}

    async def _fake_evaluate_board(
        self: RecoveryEngine,
        *,
        board_id,
        bypass_cooldown: bool = False,
    ):  # type: ignore[override]
        assert board_id == board.id
        seen["bypass_cooldown"] = bypass_cooldown
        now = utcnow()
        return [
            RecoveryIncident(
                organization_id=org.id,
                board_id=board.id,
                agent_id=agent.id,
                status="recovered",
                reason="heartbeat_stale",
                action="forced_heartbeat_resync",
                attempts=1,
                detected_at=now,
                recovered_at=now,
                created_at=now,
                updated_at=now,
            )
        ]

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    monkeypatch.setattr(RecoveryEngine, "evaluate_board", _fake_evaluate_board)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(f"/api/v1/runtime/recovery/run?board_id={board.id}&force=true")

    assert response.status_code == 200
    assert seen["bypass_cooldown"] is True
    assert response.json()["recovered"] == 1
    await engine.dispose()
