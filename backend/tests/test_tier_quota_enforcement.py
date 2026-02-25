# ruff: noqa: S101
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
from app.db.session import get_session
from app.models.installations import InstallationRequest
from app.models.organizations import Organization
from app.models.tier_quotas import TierQuota
from app.services.organizations import OrganizationContext


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(installations_router)
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
async def test_install_blocked_when_ability_slots_exhausted() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")

    async with session_maker() as session:
        session.add(org)
        session.add(
            TierQuota(
                organization_id=org.id,
                tier="personal",
                max_abilities=1,
                max_storage_mb=500,
            )
        )
        session.add(
            InstallationRequest(
                organization_id=org.id,
                package_class="skill",
                package_key="existing-skill",
                approval_mode="ask_first",
                status="approved",
                requested_payload={"estimated_storage_mb": 50},
            )
        )
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
        response = await client.post(
            "/api/v1/installations/requests",
            json={"package_class": "skill", "package_key": "new-skill"},
        )

    assert response.status_code == 409
    assert "ability slots" in response.json()["detail"].lower()
    await engine.dispose()


@pytest.mark.asyncio
async def test_storage_over_quota_returns_clear_message() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")

    async with session_maker() as session:
        session.add(org)
        session.add(
            TierQuota(
                organization_id=org.id,
                tier="personal",
                max_abilities=10,
                max_storage_mb=100,
            )
        )
        session.add(
            InstallationRequest(
                organization_id=org.id,
                package_class="library",
                package_key="existing-lib",
                approval_mode="ask_first",
                status="approved",
                requested_payload={"estimated_storage_mb": 70},
            )
        )
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
        response = await client.post(
            "/api/v1/installations/requests",
            json={
                "package_class": "library",
                "package_key": "large-lib",
                "requested_payload": {"estimated_storage_mb": 40},
            },
        )

    assert response.status_code == 409
    assert "storage quota" in response.json()["detail"].lower()
    await engine.dispose()
