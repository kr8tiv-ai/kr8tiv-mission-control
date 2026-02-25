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
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
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
    member = OrganizationMember(
        organization_id=org.id,
        user_id=uuid4(),
        role="owner",
        all_boards_read=True,
        all_boards_write=True,
    )
    return OrganizationContext(organization=org, member=member)


@pytest.mark.asyncio
async def test_install_request_requires_owner_approval_by_default() -> None:
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
        response = await client.post(
            "/api/v1/installations/requests",
            json={
                "package_class": "automation",
                "package_key": "uplay-chromium",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["approval_mode"] == "ask_first"
    assert body["status"] == "pending_owner_approval"
    assert body["approved_at"] is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_break_glass_requires_reason_and_ttl() -> None:
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
        missing_reason = await client.post(
            "/api/v1/installations/override/start",
            json={"reason": "", "ttl_minutes": 30},
        )
        invalid_ttl = await client.post(
            "/api/v1/installations/override/start",
            json={"reason": "Emergency recovery", "ttl_minutes": 0},
        )
        success = await client.post(
            "/api/v1/installations/override/start",
            json={"reason": "Emergency recovery", "ttl_minutes": 30},
        )

    assert missing_reason.status_code == 422
    assert invalid_ttl.status_code == 422
    assert success.status_code == 200
    body = success.json()
    assert body["active"] is True
    assert body["reason"] == "Emergency recovery"
    await engine.dispose()
