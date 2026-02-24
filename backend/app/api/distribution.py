"""API routes for generating and downloading kr8tiv-claw distribution bundles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import require_org_admin
from app.schemas.distribution import (
    DistributionArtifactMetadata,
    DistributionGenerateRequest,
    DistributionGenerateResult,
)
from app.services.distribution_service import DistributionService

if TYPE_CHECKING:
    from app.services.organizations import OrganizationContext

router = APIRouter(prefix="/distribution", tags=["distribution"])
ORG_ADMIN_DEP = Depends(require_org_admin)


def get_distribution_service() -> DistributionService:
    """Build a distribution service instance for request-scoped handlers."""
    return DistributionService()


SERVICE_DEP = Depends(get_distribution_service)


@router.post("/generate", response_model=DistributionGenerateResult)
async def generate_distribution_bundle(
    payload: DistributionGenerateRequest,
    _ctx: OrganizationContext = ORG_ADMIN_DEP,
    service: DistributionService = SERVICE_DEP,
) -> DistributionGenerateResult:
    """Generate tenant workspace/config/compose artifacts from a harness bundle."""
    try:
        return await service.generate_bundle(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/artifacts/{tenant_id}", response_model=DistributionArtifactMetadata)
async def get_distribution_artifact_metadata(
    tenant_id: str,
    _ctx: OrganizationContext = ORG_ADMIN_DEP,
    service: DistributionService = SERVICE_DEP,
) -> DistributionArtifactMetadata:
    """Return metadata and file listing for a generated tenant artifact bundle."""
    try:
        return service.get_artifact_metadata(tenant_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/artifacts/{tenant_id}/download")
async def download_distribution_artifact(
    tenant_id: str,
    _ctx: OrganizationContext = ORG_ADMIN_DEP,
    service: DistributionService = SERVICE_DEP,
) -> FileResponse:
    """Create and return a zip archive for a generated tenant artifact bundle."""
    try:
        archive = service.create_download_archive(tenant_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(
        path=archive,
        filename=archive.name,
        media_type="application/zip",
    )
