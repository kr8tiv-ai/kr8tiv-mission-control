# ruff: noqa: S101
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.gsd_runs import router as gsd_runs_router
from app.api.verification_ops import router as verification_ops_router
from app.core.time import utcnow
from app.db.session import get_session
from app.models.boards import Board
from app.models.gsd_runs import GSDRun
from app.models.organizations import Organization
from app.services.organizations import OrganizationContext


@dataclass(slots=True)
class _FakeCheck:
    name: str
    required: bool
    passed: bool
    detail: str


@dataclass(slots=True)
class _FakeVerificationResult:
    checks: list[_FakeCheck]
    all_passed: bool
    required_failed: int
    generated_at: datetime = field(default_factory=datetime.utcnow)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(verification_ops_router)
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
async def test_execute_verification_returns_pass_fail_matrix(
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

    from app.api import verification_ops

    async def _fake_run_verification(*, route_paths: set[str], profile: str) -> _FakeVerificationResult:
        assert profile == "auto"
        assert "/api/v1/runtime/verification/execute" in route_paths
        return _FakeVerificationResult(
            checks=[
                _FakeCheck(name="health_routes", required=True, passed=True, detail="ok"),
                _FakeCheck(
                    name="notebook_capability",
                    required=True,
                    passed=False,
                    detail="misconfig:runner_missing",
                ),
            ],
            all_passed=False,
            required_failed=1,
        )

    monkeypatch.setattr(verification_ops, "run_verification_harness", _fake_run_verification)
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/v1/runtime/verification/execute")

    assert response.status_code == 200
    body = response.json()
    assert body["all_passed"] is False
    assert body["required_failed"] == 1
    assert len(body["checks"]) == 2
    assert body["checks"][1]["name"] == "notebook_capability"
    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_verification_links_evidence_into_gsd_run(
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
        run_name="phase25-validation",
        stage="validation",
        status="in_progress",
        rollout_evidence_links=[],
        metrics_snapshot={},
        created_at=utcnow(),
        updated_at=utcnow(),
    )

    async with session_maker() as session:
        session.add(org)
        session.add(board)
        session.add(run)
        await session.commit()

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return _org_context(org)

    from app.api import verification_ops

    async def _fake_run_verification(*, route_paths: set[str], profile: str) -> _FakeVerificationResult:
        return _FakeVerificationResult(
            checks=[
                _FakeCheck(name="health_routes", required=True, passed=True, detail="ok"),
                _FakeCheck(name="notebook_capability", required=True, passed=True, detail="ready:ok"),
            ],
            all_passed=True,
            required_failed=0,
        )

    monkeypatch.setattr(verification_ops, "run_verification_harness", _fake_run_verification)
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(f"/api/v1/runtime/verification/execute?gsd_run_id={run.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["gsd_run_updated"] is True
    assert body["evidence_link"]

    async with session_maker() as session:
        refreshed = await GSDRun.objects.by_id(run.id).first(session)
        assert refreshed is not None
        assert refreshed.status == "in_progress"
        assert body["evidence_link"] in refreshed.rollout_evidence_links
        assert refreshed.metrics_snapshot["verification_checks_total"] == 2
        assert refreshed.metrics_snapshot["verification_required_failed"] == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_verification_blocks_gsd_run_when_required_checks_fail(
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
        run_name="phase25-validation",
        stage="validation",
        status="in_progress",
        rollout_evidence_links=[],
        metrics_snapshot={},
        created_at=utcnow(),
        updated_at=utcnow(),
    )

    async with session_maker() as session:
        session.add(org)
        session.add(board)
        session.add(run)
        await session.commit()

    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return _org_context(org)

    from app.api import verification_ops

    async def _fake_run_verification(*, route_paths: set[str], profile: str) -> _FakeVerificationResult:
        return _FakeVerificationResult(
            checks=[
                _FakeCheck(name="health_routes", required=True, passed=True, detail="ok"),
                _FakeCheck(
                    name="notebook_capability",
                    required=True,
                    passed=False,
                    detail="misconfig:runner_missing",
                ),
            ],
            all_passed=False,
            required_failed=1,
        )

    monkeypatch.setattr(verification_ops, "run_verification_harness", _fake_run_verification)
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(f"/api/v1/runtime/verification/execute?gsd_run_id={run.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["all_passed"] is False
    assert body["required_failed"] == 1

    async with session_maker() as session:
        refreshed = await GSDRun.objects.by_id(run.id).first(session)
        assert refreshed is not None
        assert refreshed.status == "blocked"
        assert refreshed.metrics_snapshot["verification_required_failed"] == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_verification_requires_admin() -> None:
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
        response = await client.post("/api/v1/runtime/verification/execute")

    assert response.status_code == 403
    await engine.dispose()
