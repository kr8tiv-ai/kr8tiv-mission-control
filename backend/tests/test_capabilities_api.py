# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.capabilities import router as capabilities_router
from app.api.deps import require_org_admin, require_org_member
from app.db.session import get_session
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.services.organizations import OrganizationContext


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(capabilities_router)
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
async def test_create_skill_library_device_records_requires_admin() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return _org_context(org)

    async def _override_require_org_member() -> OrganizationContext:
        return _org_context(org)

    app = _build_test_app()
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    app.dependency_overrides[require_org_member] = _override_require_org_member

    async with session_maker() as session:
        session.add(org)
        await session.commit()

    payloads = [
        {"capability_type": "skill", "key": "task-routing", "name": "Task Routing"},
        {"capability_type": "library", "key": "pandas", "name": "Pandas"},
        {"capability_type": "device", "key": "tailscale-laptop", "name": "Tailscale Laptop"},
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        for payload in payloads:
            response = await client.post("/api/v1/capabilities", json=payload)
            assert response.status_code == 200
            body = response.json()
            assert body["capability_type"] == payload["capability_type"]
            assert body["key"] == payload["key"]
            assert body["name"] == payload["name"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_capability_blocks_non_admin() -> None:
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
        response = await client.post(
            "/api/v1/capabilities",
            json={
                "capability_type": "skill",
                "key": "task-routing",
                "name": "Task Routing",
            },
        )

    assert response.status_code == 403
    await engine.dispose()
