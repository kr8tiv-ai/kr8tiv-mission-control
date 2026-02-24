# ruff: noqa: INP001

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.installations import router as installations_router
from app.db.session import get_session
from app.models.installations import InstallationRequest
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.override_sessions import OverrideSession
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
async def test_install_request_requires_owner_approval_by_default() -> None:
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
            create_response = await client.post(
                "/api/v1/installations/requests",
                json={
                    "title": "Install supermemory plugin",
                    "install_command": "openclaw plugins install @supermemory/openclaw-supermemory",
                },
            )
            assert create_response.status_code == 201
            created = create_response.json()
            assert created["approval_mode"] == "ask_first"
            assert created["status"] == "pending_owner_approval"

            execute_response = await client.post(
                f"/api/v1/installations/requests/{created['id']}/execute",
                json={},
            )
            assert execute_response.status_code == 409
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_break_glass_requires_reason_and_ttl() -> None:
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
            create_response = await client.post(
                "/api/v1/installations/requests",
                json={
                    "title": "Install tailscale bridge",
                    "install_command": "tailscale up",
                },
            )
            assert create_response.status_code == 201
            request_id = create_response.json()["id"]

            missing_reason = await client.post(
                "/api/v1/installations/override-sessions",
                json={"ttl_minutes": 30},
            )
            assert missing_reason.status_code == 422

            missing_ttl = await client.post(
                "/api/v1/installations/override-sessions",
                json={"reason": "critical incident"},
            )
            assert missing_ttl.status_code == 422

            valid_override = await client.post(
                "/api/v1/installations/override-sessions",
                json={
                    "reason": "Critical outage mitigation",
                    "ttl_minutes": 30,
                },
            )
            assert valid_override.status_code == 201
            override_id = valid_override.json()["id"]

            execute_response = await client.post(
                f"/api/v1/installations/requests/{request_id}/execute",
                json={"override_session_id": override_id},
            )
            assert execute_response.status_code == 200
            assert execute_response.json()["executed"] is True

        async with session_maker() as session:
            request = (
                await session.exec(
                    select(InstallationRequest).where(InstallationRequest.id == UUID(request_id)),
                )
            ).first()
            assert request is not None
            assert request.status == "executed"
            assert request.override_session_id == UUID(override_id)

            override = (
                await session.exec(
                    select(OverrideSession).where(OverrideSession.id == UUID(override_id)),
                )
            ).first()
            assert override is not None
            assert override.reason == "Critical outage mitigation"
    finally:
        await engine.dispose()
