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
from app.api.installations import router as installations_router
from app.api.tier_quotas import router as tier_quotas_router
from app.db.session import get_session
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
    api_v1.include_router(tier_quotas_router)
    api_v1.include_router(installations_router)
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


@pytest.mark.asyncio
async def test_install_blocked_when_ability_slots_exhausted() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with session_maker() as session:
            organization = Organization(id=uuid4(), name="Org One")
            session.add(organization)
            await session.commit()

        app = _build_test_app(session_maker, organization=organization)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            quota_response = await client.post(
                "/api/v1/tier-quotas",
                json={
                    "tier_name": "hatchling",
                    "max_abilities": 1,
                    "max_storage_mb": 500,
                },
            )
            assert quota_response.status_code == 201

            first_install = await client.post(
                "/api/v1/installations/requests",
                json={
                    "title": "Install supermemory plugin",
                    "install_command": "openclaw plugins install @supermemory/openclaw-supermemory",
                },
            )
            assert first_install.status_code == 201

            second_install = await client.post(
                "/api/v1/installations/requests",
                json={
                    "title": "Install voice pack",
                    "install_command": "openclaw plugins install @kr8tiv/voice-pack",
                },
            )
            assert second_install.status_code == 409
            assert "ability slots" in second_install.json()["detail"].lower()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_storage_over_quota_returns_clear_message() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with session_maker() as session:
            organization = Organization(id=uuid4(), name="Org One")
            session.add(organization)
            await session.commit()

        app = _build_test_app(session_maker, organization=organization)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            quota_response = await client.post(
                "/api/v1/tier-quotas",
                json={
                    "tier_name": "hatchling",
                    "max_abilities": 5,
                    "max_storage_mb": 50,
                },
            )
            assert quota_response.status_code == 201

            first_install = await client.post(
                "/api/v1/installations/requests",
                json={
                    "title": "Install plugin A",
                    "install_command": "openclaw plugins install @a/plugin",
                    "requested_payload": {"storage_mb": 40},
                },
            )
            assert first_install.status_code == 201

            second_install = await client.post(
                "/api/v1/installations/requests",
                json={
                    "title": "Install plugin B",
                    "install_command": "openclaw plugins install @b/plugin",
                    "requested_payload": {"storage_mb": 20},
                },
            )
            assert second_install.status_code == 409
            assert "storage quota" in second_install.json()["detail"].lower()
    finally:
        await engine.dispose()
