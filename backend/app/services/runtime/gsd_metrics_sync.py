"""Sync runtime recovery summaries into GSD run telemetry rows."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.core.time import utcnow
from app.models.gsd_runs import GSDRun
from app.services.runtime.gsd_metrics_aggregator import aggregate_continuity_metrics

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def sync_recovery_summary_to_gsd_run(
    *,
    session: AsyncSession,
    organization_id: UUID,
    board_id: UUID,
    gsd_run_id: UUID,
    total_incidents: int,
    recovered: int,
    failed: int,
    suppressed: int,
) -> GSDRun | None:
    """Persist recovery counters in a target GSD run metrics snapshot."""
    row = await GSDRun.objects.by_id(gsd_run_id).first(session)
    if row is None or row.organization_id != organization_id:
        return None
    if row.board_id is not None and row.board_id != board_id:
        return None

    snapshot = aggregate_continuity_metrics(
        existing=row.metrics_snapshot,
        total_incidents=total_incidents,
        recovered=recovered,
        failed=failed,
        suppressed=suppressed,
    )
    row.metrics_snapshot = snapshot
    row.updated_at = utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
