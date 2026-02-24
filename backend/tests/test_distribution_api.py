# ruff: noqa: S101
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.distribution import get_distribution_service
from app.api.distribution import router as distribution_router
from app.db.session import get_session
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.schemas.distribution import (
    DistributionArtifactMetadata,
    DistributionGenerateRequest,
    DistributionGenerateResult,
)
from app.services.organizations import OrganizationContext


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(distribution_router)
    app.include_router(api_v1)
    return app


class _FakeDistributionService:
    async def generate_bundle(self, request: DistributionGenerateRequest) -> DistributionGenerateResult:
        return DistributionGenerateResult(
            tenant_id=f"{request.tenant_slug}-1234abcd",
            tenant_slug=request.tenant_slug,
            include_watchdog=request.include_watchdog,
            artifact_dir=Path("/tmp/artifacts"),
            files=["openclaw.json", "docker-compose.tenant.yml"],
            created_at=datetime(2026, 2, 24, tzinfo=UTC),
        )

    def get_artifact_metadata(self, tenant_id: str) -> DistributionArtifactMetadata:
        return DistributionArtifactMetadata(
            tenant_id=tenant_id,
            tenant_slug="acme-support",
            artifact_dir=Path("/tmp/artifacts"),
            files=["openclaw.json", "docker-compose.tenant.yml"],
            include_watchdog=True,
            created_at=datetime(2026, 2, 24, tzinfo=UTC),
        )

    def create_download_archive(self, tenant_id: str) -> Path:
        return Path(f"/tmp/{tenant_id}.zip")


@pytest.mark.asyncio
async def test_distribution_generate_endpoint_returns_metadata() -> None:
    app = _build_test_app()

    async def _override_get_session() -> AsyncSession:  # pragma: no cover - not used
        msg = "session should not be requested"
        raise AssertionError(msg)

    async def _override_require_org_admin() -> OrganizationContext:
        org = Organization(id=uuid4(), name="Org")
        member = OrganizationMember(
            organization_id=org.id,
            user_id=uuid4(),
            role="owner",
            all_boards_read=True,
            all_boards_write=True,
        )
        return OrganizationContext(organization=org, member=member)

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    app.dependency_overrides[get_distribution_service] = lambda: _FakeDistributionService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/distribution/generate",
            json={
                "tenant_slug": "acme-support",
                "harness_yaml": "tenant:\n  slug: acme-support\n",
                "include_watchdog": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "acme-support-1234abcd"
    assert "openclaw.json" in body["files"]


@pytest.mark.asyncio
async def test_distribution_endpoints_enforce_org_admin_authz() -> None:
    app = _build_test_app()

    async def _deny_org_admin() -> OrganizationContext:
        raise HTTPException(status_code=403, detail="forbidden")

    app.dependency_overrides[require_org_admin] = _deny_org_admin
    app.dependency_overrides[get_distribution_service] = lambda: _FakeDistributionService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/distribution/generate",
            json={
                "tenant_slug": "acme-support",
                "harness_yaml": "tenant:\n  slug: acme-support\n",
                "include_watchdog": False,
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_distribution_download_returns_archive(
    tmp_path: Path,
) -> None:
    app = _build_test_app()

    class _DownloadService(_FakeDistributionService):
        def create_download_archive(self, tenant_id: str) -> Path:
            archive = tmp_path / f"{tenant_id}.zip"
            archive.write_bytes(b"zip-content")
            return archive

    async def _override_require_org_admin() -> OrganizationContext:
        org = Organization(id=uuid4(), name="Org")
        member = OrganizationMember(
            organization_id=org.id,
            user_id=uuid4(),
            role="owner",
            all_boards_read=True,
            all_boards_write=True,
        )
        return OrganizationContext(organization=org, member=member)

    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    app.dependency_overrides[get_distribution_service] = lambda: _DownloadService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/distribution/artifacts/acme-1234abcd/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "filename=" in response.headers["content-disposition"].lower()
