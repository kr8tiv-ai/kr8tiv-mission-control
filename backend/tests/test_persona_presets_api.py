# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.persona_presets import router as persona_presets_router
from app.db.session import get_session
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.persona_presets import PersonaPreset
from app.services.organizations import OrganizationContext


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(persona_presets_router)
    app.include_router(api_v1)
    return app


async def _create_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)


async def _seed_data(session: AsyncSession) -> tuple[Organization, Agent, PersonaPreset]:
    org = Organization(id=uuid4(), name="KR8TIV")
    member = OrganizationMember(
        organization_id=org.id,
        user_id=uuid4(),
        role="owner",
        all_boards_read=True,
        all_boards_write=True,
    )
    gateway = Gateway(
        id=uuid4(),
        organization_id=org.id,
        name="main-gateway",
        url="ws://gateway.example/ws",
        workspace_root="/tmp/openclaw",
    )
    board = Board(
        id=uuid4(),
        organization_id=org.id,
        name="main-board",
        slug="main-board",
        gateway_id=gateway.id,
    )
    agent = Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=gateway.id,
        name="Friday",
        identity_profile={"role": "generalist"},
        identity_template="legacy identity",
        soul_template="legacy soul",
    )
    preset = PersonaPreset(
        id=uuid4(),
        organization_id=org.id,
        key="business-cmo",
        name="Business CMO",
        deployment_mode="team",
        identity_profile={"role": "CMO", "communication_style": "sharp"},
        identity_template="new identity template",
        soul_template="new soul template",
        metadata_={"tier": "enterprise"},
    )
    session.add(org)
    session.add(member)
    session.add(gateway)
    session.add(board)
    session.add(agent)
    session.add(preset)
    await session.commit()
    return org, agent, preset


@pytest.mark.asyncio
async def test_apply_persona_preset_updates_agent_templates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_maker() as session:
        org, agent, preset = await _seed_data(session)

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        member = OrganizationMember(
            organization_id=org.id,
            user_id=uuid4(),
            role="owner",
            all_boards_read=True,
            all_boards_write=True,
        )
        return OrganizationContext(organization=org, member=member)

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            f"/api/v1/persona-presets/agents/{agent.id}/apply",
            json={"preset_id": str(preset.id)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["agent_id"] == str(agent.id)
    assert body["preset_id"] == str(preset.id)

    async with session_maker() as verify_session:
        updated_agent = await Agent.objects.by_id(agent.id).first(verify_session)
        assert updated_agent is not None
        assert updated_agent.identity_profile == {
            "role": "CMO",
            "communication_style": "sharp",
        }
        assert updated_agent.identity_template == "new identity template"
        assert updated_agent.soul_template == "new soul template"

    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_persona_preset_enforces_org_admin_access() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        _org, agent, preset = await _seed_data(session)

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _deny_org_admin() -> OrganizationContext:
        raise HTTPException(status_code=403, detail="forbidden")

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _deny_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            f"/api/v1/persona-presets/agents/{agent.id}/apply",
            json={"preset_id": str(preset.id)},
        )

    assert response.status_code == 403
    await engine.dispose()
