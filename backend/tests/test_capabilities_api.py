# ruff: noqa: INP001

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.capabilities import router as capabilities_router
from app.api.deps import require_org_admin
from app.db.session import get_session
from app.models.capabilities import Capability
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
    allow_admin: bool,
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(capabilities_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    if allow_admin:

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

    else:

        async def _override_require_org_admin() -> OrganizationContext:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


@pytest.mark.asyncio
async def test_create_skill_library_device_records_requires_admin() -> None:
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

        app = _build_test_app(
            session_maker,
            organization=organization,
            allow_admin=False,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/capabilities",
                json={
                    "kind": "skill",
                    "name": "Research Synthesizer",
                    "risk_level": "medium",
                    "scope": "team",
                },
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_capabilities_catalog_create_and_list_by_kind() -> None:
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

        app = _build_test_app(
            session_maker,
            organization=organization,
            allow_admin=True,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            payloads = [
                {
                    "kind": "skill",
                    "name": "Research Synthesizer",
                    "description": "Summarizes long technical documents.",
                    "risk_level": "medium",
                    "scope": "team",
                    "metadata": {"source": "marketplace"},
                },
                {
                    "kind": "library",
                    "name": "LangGraph",
                    "description": "Stateful graph orchestration runtime.",
                    "risk_level": "low",
                    "scope": "team",
                    "metadata": {"package": "langgraph"},
                },
                {
                    "kind": "device",
                    "name": "Owner Laptop",
                    "description": "Primary owner workstation via encrypted tunnel.",
                    "risk_level": "high",
                    "scope": "individual",
                    "metadata": {
                        "access_method": "tailscale",
                        "encryption": "wireguard",
                    },
                },
            ]
            for payload in payloads:
                response = await client.post("/api/v1/capabilities", json=payload)
                assert response.status_code == status.HTTP_201_CREATED

            list_response = await client.get("/api/v1/capabilities")
            assert list_response.status_code == status.HTTP_200_OK
            listed = list_response.json()
            assert len(listed) == 3
            assert {item["kind"] for item in listed} == {"skill", "library", "device"}

            device_response = await client.get("/api/v1/capabilities", params={"kind": "device"})
            assert device_response.status_code == status.HTTP_200_OK
            device_items = device_response.json()
            assert len(device_items) == 1
            assert device_items[0]["metadata"]["access_method"] == "tailscale"

        async with session_maker() as session:
            rows = (await session.exec(select(Capability))).all()
            assert len(rows) == 3
    finally:
        await engine.dispose()
