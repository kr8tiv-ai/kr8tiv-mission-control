"""Schemas for kr8tiv-claw distribution bundle generation APIs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import StringConstraints
from sqlmodel import Field, SQLModel

TenantSlug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    ),
]
HarnessYaml = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DistributionGenerateRequest(SQLModel):
    """Request payload for generating a tenant distribution bundle."""

    tenant_slug: TenantSlug
    harness_yaml: HarnessYaml
    include_watchdog: bool = False


class DistributionArtifactMetadata(SQLModel):
    """Artifact metadata returned by distribution generation/read endpoints."""

    tenant_id: str
    tenant_slug: str
    artifact_dir: Path
    files: list[str] = Field(default_factory=list)
    include_watchdog: bool
    created_at: datetime


class DistributionGenerateResult(DistributionArtifactMetadata):
    """Response payload returned by distribution generation endpoint."""
