# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.backups import router as backups_router
from app.api.deps import require_org_admin
from app.db.session import get_session
from app.models.organizations import Organization
from app.services.organizations import OrganizationContext


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(backups_router)
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
async def test_twice_weekly_backup_reminder_emits_warning_when_unconfirmed() -> None:
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
        response = await client.get("/api/v1/backups/reminder")

    assert response.status_code == 200
    body = response.json()
    assert body["reminder_due"] is True
    assert body["cadence_per_week"] == 2
    assert "lose all your information" in body["warning"].lower()
    await engine.dispose()


@pytest.mark.asyncio
async def test_backup_confirmation_records_destination_without_payload() -> None:
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
            "/api/v1/backups/confirm",
            json={
                "wants_backup": True,
                "destination_type": "local_drive",
                "destination_label": "D:/KR8TIV/KIN",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["destination_type"] == "local_drive"
    assert body["stores_customer_payload"] is False
    await engine.dispose()


@pytest.mark.asyncio
async def test_backup_confirmation_accepts_multiple_destination_types() -> None:
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

    destinations = ["local_drive", "external_drive", "customer_cloud", "manual_export"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        for destination in destinations:
            response = await client.post(
                "/api/v1/backups/confirm",
                json={"wants_backup": True, "destination_type": destination},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["destination_type"] == destination
            assert body["status"] == "confirmed"
    await engine.dispose()
