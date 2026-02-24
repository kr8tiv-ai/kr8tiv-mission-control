# ruff: noqa: INP001

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.persona_presets import router as persona_presets_router
from app.db.session import get_session
from app.models.agents import Agent
from app.models.gateways import Gateway
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.services.organizations import OrganizationContext


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def _build_test_app(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    organization: Organization,
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(persona_presets_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return OrganizationContext(
            organization=organization,
            member=OrganizationMember(
                organization_id=organization.id,
                user_id=uuid4(),
                role="owner",
                all_boards_read=True,
                all_boards_write=True,
            ),
        )

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


async def _seed_org_agent(session: AsyncSession) -> tuple[Organization, Agent]:
    organization = Organization(id=uuid4(), name="Org One")
    gateway = Gateway(
        id=uuid4(),
        organization_id=organization.id,
        name="Gateway One",
        url="https://gateway.example.local",
        workspace_root="/workspace/openclaw",
    )
    agent = Agent(
        id=uuid4(),
        gateway_id=gateway.id,
        name="Friday",
        status="online",
        identity_profile={"role": "old"},
        identity_template="old identity",
        soul_template="old soul",
    )
    session.add(organization)
    session.add(gateway)
    session.add(agent)
    await session.commit()
    return organization, agent


@pytest.mark.asyncio
async def test_apply_persona_preset_updates_agent_templates() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with session_maker() as session:
            organization, agent = await _seed_org_agent(session)

        app = _build_test_app(session_maker, organization=organization)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            create_response = await client.post(
                "/api/v1/persona-presets",
                json={
                    "name": "Friday CMO Persona",
                    "description": "CMO-focused voice",
                    "preset_mode": "team",
                    "identity_profile": {
                        "role": "CMO",
                        "communication_style": "direct, strategic",
                    },
                    "identity_template": "You are Friday, strategic CMO.",
                    "soul_template": "Protect brand voice and move fast with evidence.",
                },
            )

            assert create_response.status_code == 201
            preset_id = create_response.json()["id"]

            apply_response = await client.post(
                f"/api/v1/persona-presets/agents/{agent.id}/apply",
                json={"preset_id": preset_id},
            )

        assert apply_response.status_code == 200
        body = apply_response.json()
        assert body["applied"] is True
        assert body["agent_id"] == str(agent.id)
        assert body["preset_id"] == preset_id

        async with session_maker() as session:
            refreshed = await session.get(Agent, agent.id)
            assert refreshed is not None
            assert refreshed.identity_profile == {
                "role": "CMO",
                "communication_style": "direct, strategic",
            }
            assert refreshed.identity_template == "You are Friday, strategic CMO."
            assert refreshed.soul_template == "Protect brand voice and move fast with evidence."
    finally:
        await engine.dispose()
