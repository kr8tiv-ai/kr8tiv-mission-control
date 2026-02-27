# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.runtime_ops import router as runtime_ops_router
from app.core.time import utcnow
from app.db.session import get_session
from app.models.boards import Board
from app.models.gsd_runs import GSDRun
from app.models.organizations import Organization
from app.models.tasks import Task
from app.services.notebooklm_capability_gate import NotebookCapabilityGateResult
from app.services.organizations import OrganizationContext
from app.services.runtime.verification_harness import (
    VerificationCheckResult,
    VerificationHarnessResult,
)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(runtime_ops_router)
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
async def test_control_plane_status_requires_admin() -> None:
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
        response = await client.get("/api/v1/runtime/ops/control-plane-status")

    assert response.status_code == 403
    await engine.dispose()


@pytest.mark.asyncio
async def test_control_plane_status_returns_aggregated_runtime_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _create_schema(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    org = Organization(id=uuid4(), name="KR8TIV")
    board = Board(id=uuid4(), organization_id=org.id, name="Ops", slug="ops")
    run = GSDRun(
        id=uuid4(),
        organization_id=org.id,
        board_id=board.id,
        run_name="phase25",
        stage="validation",
        status="blocked",
        owner_approval_required=False,
        owner_approval_status="not_required",
        rollout_evidence_links=[],
        metrics_snapshot={"verification_required_failed": 2},
        created_at=utcnow(),
        updated_at=utcnow(),
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
            )
        )
        session.add(
            Task(
                board_id=board.id,
                title="Notebook retryable",
                task_mode="arena_notebook",
                notebook_gate_state="retryable",
            )
        )
        session.add(run)
        await session.commit()

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return _org_context(org)

    from app.api import runtime_ops

    async def _fake_notebook_gate(**_kwargs) -> NotebookCapabilityGateResult:
        return NotebookCapabilityGateResult(
            state="ready",
            reason="ok",
            operator_message="NotebookLM capability gate passed.",
            checked_at=utcnow(),
            selected_profile="personal",
            notebook_count=4,
        )

    async def _fake_verification_harness(
        *,
        route_paths: set[str],
        profile: str = "auto",
    ) -> VerificationHarnessResult:
        assert profile == "auto"
        assert "/api/v1/runtime/ops/control-plane-status" in route_paths
        return VerificationHarnessResult(
            generated_at=utcnow(),
            checks=[
                VerificationCheckResult(
                    name="health_routes",
                    required=True,
                    passed=True,
                    detail="ok",
                ),
                VerificationCheckResult(
                    name="recovery_run_route",
                    required=True,
                    passed=False,
                    detail="missing_routes:/api/v1/runtime/recovery/run",
                ),
            ],
            all_passed=False,
            required_failed=1,
        )

    monkeypatch.setattr(runtime_ops, "evaluate_notebooklm_capability", _fake_notebook_gate)
    monkeypatch.setattr(runtime_ops, "run_verification_harness", _fake_verification_harness)

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            f"/api/v1/runtime/ops/control-plane-status?board_id={board.id}&profile=auto"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["arena"]["healthy"] is True
    assert "arsenal" in body["arena"]["configured_agents"]

    assert body["notebook"]["state"] == "ready"
    assert body["notebook"]["reason"] == "ok"
    assert body["notebook"]["total_notebook_tasks"] == 2
    assert body["notebook"]["gate_counts"]["ready"] == 1
    assert body["notebook"]["gate_counts"]["retryable"] == 1

    assert body["verification"]["all_passed"] is False
    assert body["verification"]["required_failed"] == 1
    assert body["verification"]["failed_check_names"] == ["recovery_run_route"]

    assert body["gsd"]["latest_status"] == "blocked"
    assert body["gsd"]["is_blocked"] is True
    assert body["gsd"]["verification_required_failed"] == 2

    await engine.dispose()
