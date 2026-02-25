# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.change_requests import router as change_requests_router
from app.api.deps import require_org_admin
from app.db.session import get_session
from app.models.organizations import Organization
from app.services.organizations import OrganizationContext


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(change_requests_router)
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
async def test_customer_can_submit_and_track_change_request() -> None:
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
        created = await client.post(
            "/api/v1/change-requests",
            json={
                "title": "Enable WhatsApp group routing",
                "description": "Add shared channel routing for owner + team group context.",
                "category": "integration",
                "priority": "high",
            },
        )
        assert created.status_code == 200
        created_body = created.json()
        assert created_body["status"] == "submitted"

        request_id = created_body["id"]
        triage = await client.patch(
            f"/api/v1/change-requests/{request_id}",
            json={"status": "triage", "resolution_note": "Queued for review"},
        )
        assert triage.status_code == 200
        assert triage.json()["status"] == "triage"

        approved = await client.patch(
            f"/api/v1/change-requests/{request_id}",
            json={"status": "approved", "resolution_note": "Approved for next sprint"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        fetched = await client.get(f"/api/v1/change-requests/{request_id}")
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["status"] == "approved"
        assert body["priority"] == "high"
    await engine.dispose()
