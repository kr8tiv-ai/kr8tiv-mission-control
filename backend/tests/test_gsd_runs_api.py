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
from app.api.gsd_runs import router as gsd_runs_router
from app.db.session import get_session
from app.models.boards import Board
from app.models.organizations import Organization
from app.services.organizations import OrganizationContext


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(gsd_runs_router)
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
async def test_gsd_run_tracks_stage_progress_owner_approval_and_rollout_evidence() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")
    board = Board(id=uuid4(), organization_id=org.id, name="MC", slug="mc")

    async with session_maker() as session:
        session.add(org)
        session.add(board)
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
            "/api/v1/gsd-runs",
            json={
                "board_id": str(board.id),
                "run_name": "phase15-hardening",
                "stage": "planning",
                "status": "in_progress",
                "owner_approval_required": True,
                "owner_approval_status": "pending",
            },
        )
        assert created.status_code == 200
        run_id = created.json()["id"]

        for stage in ["implementation", "rollout", "validation", "hardening"]:
            payload = {
                "stage": stage,
                "status": "in_progress" if stage != "hardening" else "completed",
            }
            if stage == "rollout":
                payload["rollout_evidence_links"] = [
                    "https://example.com/release/phase15",
                    "https://example.com/healthchecks/phase15",
                ]
            if stage == "validation":
                payload["owner_approval_status"] = "approved"
                payload["owner_approval_note"] = "Verified with owner on call."

            updated = await client.patch(f"/api/v1/gsd-runs/{run_id}", json=payload)
            assert updated.status_code == 200
            assert updated.json()["stage"] == stage

        fetched = await client.get(f"/api/v1/gsd-runs/{run_id}")
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["stage"] == "hardening"
        assert body["status"] == "completed"
        assert body["owner_approval_status"] == "approved"
        assert body["owner_approval_required"] is True
        assert len(body["rollout_evidence_links"]) == 2
        assert body["completed_at"] is not None


@pytest.mark.asyncio
async def test_gsd_run_list_is_scoped_to_current_organization() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")
    board = Board(id=uuid4(), organization_id=org.id, name="MC", slug="mc")

    async with session_maker() as session:
        session.add(org)
        session.add(board)
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
        one = await client.post(
            "/api/v1/gsd-runs",
            json={"board_id": str(board.id), "run_name": "a", "stage": "planning"},
        )
        two = await client.post(
            "/api/v1/gsd-runs",
            json={"board_id": str(board.id), "run_name": "b", "stage": "implementation"},
        )
        assert one.status_code == 200
        assert two.status_code == 200

        listed = await client.get(f"/api/v1/gsd-runs?board_id={board.id}")
        assert listed.status_code == 200
        body = listed.json()
        assert len(body) == 2
        names = {row["run_name"] for row in body}
        assert names == {"a", "b"}

    await engine.dispose()

