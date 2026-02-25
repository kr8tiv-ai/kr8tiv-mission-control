# ruff: noqa: S101
from __future__ import annotations

from collections import namedtuple

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import ActorContext, require_admin_or_agent
from app.api.runtime_ops import router as runtime_ops_router
from app.services.runtime.disk_guard import DiskGuardService

DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(runtime_ops_router)
    app.include_router(api_v1)
    return app


def test_disk_guard_maps_warning_severity_and_actions() -> None:
    service = DiskGuardService(
        path="/",
        warning_threshold_pct=80.0,
        critical_threshold_pct=90.0,
        usage_reader=lambda _path: DiskUsage(total=100, used=85, free=15),
    )
    status = service.read_status()
    assert status.severity == "warning"
    assert status.utilization_pct == pytest.approx(85.0)
    assert any("cleanup" in action.lower() for action in status.recommended_actions)


def test_disk_guard_maps_critical_severity_and_actions() -> None:
    service = DiskGuardService(
        path="/",
        warning_threshold_pct=80.0,
        critical_threshold_pct=90.0,
        usage_reader=lambda _path: DiskUsage(total=100, used=95, free=5),
    )
    status = service.read_status()
    assert status.severity == "critical"
    assert status.utilization_pct == pytest.approx(95.0)
    assert any("immediate" in action.lower() for action in status.recommended_actions)


@pytest.mark.asyncio
async def test_runtime_disk_guard_endpoint_surfaces_current_guard_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_test_app()

    async def _override_actor() -> ActorContext:
        return ActorContext(actor_type="agent")

    app.dependency_overrides[require_admin_or_agent] = _override_actor
    monkeypatch.setattr(
        "app.services.runtime.disk_guard.shutil.disk_usage",
        lambda _path: DiskUsage(total=100, used=72, free=28),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/runtime/ops/disk-guard")

    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "ok"
    assert body["utilization_pct"] == pytest.approx(72.0)
    assert body["thresholds"]["warning_pct"] == pytest.approx(80.0)
    assert body["thresholds"]["critical_pct"] == pytest.approx(90.0)
