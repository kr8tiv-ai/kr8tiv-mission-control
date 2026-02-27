# ruff: noqa: S101
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.notebook_ops import router as notebook_ops_router
from app.db.session import get_session
from app.models.boards import Board
from app.models.organizations import Organization
from app.models.tasks import Task
from app.services.organizations import OrganizationContext
from app.services.notebooklm_capability_gate import NotebookCapabilityGateResult


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(notebook_ops_router)
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
async def test_notebook_gate_endpoint_requires_admin() -> None:
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
        response = await client.get("/api/v1/runtime/notebook/gate")

    assert response.status_code == 403
    await engine.dispose()


@pytest.mark.asyncio
async def test_notebook_gate_endpoint_returns_gate_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    async def _fake_gate(**kwargs):
        assert kwargs["profile"] == "auto"
        return NotebookCapabilityGateResult(
            state="ready",
            reason="ok",
            operator_message="NotebookLM capability gate passed.",
            checked_at=datetime.utcnow(),
            selected_profile="personal",
            notebook_count=7,
        )

    from app.api import notebook_ops

    monkeypatch.setattr(notebook_ops, "evaluate_notebooklm_capability", _fake_gate)
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/runtime/notebook/gate?profile=auto")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "ready"
    assert body["reason"] == "ok"
    assert body["selected_profile"] == "personal"
    assert body["notebook_count"] == 7
    assert body["checked_at"] is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_notebook_gate_summary_requires_admin() -> None:
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
        response = await client.get(f"/api/v1/runtime/notebook/gate-summary?board_id={uuid4()}")

    assert response.status_code == 403
    await engine.dispose()


@pytest.mark.asyncio
async def test_notebook_gate_summary_returns_board_state_counts() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")
    board = Board(
        id=uuid4(),
        organization_id=org.id,
        name="Ops",
        slug="ops",
    )

    async with session_maker() as session:
        session.add(org)
        session.add(board)
        session.add(
            Task(
                board_id=board.id,
                title="Notebook ready",
                task_mode="notebook",
                notebook_gate_state="ready",
                notebook_gate_reason="ok",
            )
        )
        session.add(
            Task(
                board_id=board.id,
                title="Notebook retryable",
                task_mode="arena_notebook",
                notebook_gate_state="retryable",
                notebook_gate_reason="auth_expired",
            )
        )
        session.add(
            Task(
                board_id=board.id,
                title="Notebook misconfig",
                task_mode="notebook_creation",
                notebook_gate_state="misconfig",
                notebook_gate_reason="invalid_profile",
            )
        )
        session.add(
            Task(
                board_id=board.id,
                title="Notebook pending state",
                task_mode="notebook",
            )
        )
        session.add(
            Task(
                board_id=board.id,
                title="Ignored non-notebook mode",
                task_mode="standard",
                notebook_gate_state="hard_fail",
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
        response = await client.get(f"/api/v1/runtime/notebook/gate-summary?board_id={board.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["board_id"] == str(board.id)
    assert body["total_notebook_tasks"] == 4
    assert body["gate_counts"]["ready"] == 1
    assert body["gate_counts"]["retryable"] == 1
    assert body["gate_counts"]["misconfig"] == 1
    assert body["gate_counts"]["hard_fail"] == 0
    assert body["gate_counts"]["unknown"] == 1
    await engine.dispose()
