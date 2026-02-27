"""Runtime verification harness execution endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.gsd_runs import GSDRun
from app.schemas.verification_ops import VerificationCheckRead, VerificationExecuteRead
from app.services.organizations import OrganizationContext
from app.services.runtime.verification_harness import run_verification_harness

if False:  # pragma: no cover
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/runtime/verification", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)
PROFILE_QUERY = Query(default="auto")
GSD_RUN_ID_QUERY = Query(default=None)


def _collect_route_paths(request: Request) -> set[str]:
    return {
        str(route.path)
        for route in request.app.routes
        if hasattr(route, "path")
    }


def _build_evidence_link(*, run_id: UUID) -> str:
    return f"verification://{run_id}/{int(utcnow().timestamp())}"


async def _sync_verification_to_gsd_run(
    *,
    session: AsyncSession,
    organization_id: UUID,
    gsd_run_id: UUID,
    result,
) -> str:
    row = await GSDRun.objects.by_id(gsd_run_id).first(session)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GSD run not found")

    evidence_link = _build_evidence_link(run_id=row.id)
    links = [entry for entry in row.rollout_evidence_links if entry]
    if evidence_link not in links:
        links.append(evidence_link)
    row.rollout_evidence_links = links

    checks_total = len(result.checks)
    checks_passed = sum(1 for check in result.checks if check.passed)
    required_passed = sum(1 for check in result.checks if check.required and check.passed)
    snapshot = dict(row.metrics_snapshot)
    snapshot["verification_checks_total"] = checks_total
    snapshot["verification_checks_passed"] = checks_passed
    snapshot["verification_required_passed"] = required_passed
    snapshot["verification_required_failed"] = result.required_failed
    snapshot["verification_all_passed"] = 1 if result.all_passed else 0
    row.metrics_snapshot = snapshot

    if result.required_failed > 0:
        row.status = "blocked"
        row.completed_at = None

    row.updated_at = utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return evidence_link


@router.post("/execute", response_model=VerificationExecuteRead)
async def execute_verification_harness(
    request: Request,
    profile: str = PROFILE_QUERY,
    gsd_run_id: UUID | None = GSD_RUN_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> VerificationExecuteRead:
    """Run runtime verification checks and optionally gate a GSD run."""
    result = await run_verification_harness(
        route_paths=_collect_route_paths(request),
        profile=profile,
    )

    evidence_link: str | None = None
    gsd_run_updated = False
    if gsd_run_id is not None:
        evidence_link = await _sync_verification_to_gsd_run(
            session=session,
            organization_id=ctx.organization.id,
            gsd_run_id=gsd_run_id,
            result=result,
        )
        gsd_run_updated = True

    return VerificationExecuteRead(
        generated_at=result.generated_at,
        all_passed=result.all_passed,
        required_failed=result.required_failed,
        checks=[
            VerificationCheckRead(
                name=check.name,
                required=check.required,
                passed=check.passed,
                detail=check.detail,
            )
            for check in result.checks
        ],
        gsd_run_updated=gsd_run_updated,
        evidence_link=evidence_link,
    )
