"""Background worker execution for deterministic run telemetry evaluation."""

from __future__ import annotations

from sqlmodel import col, select

from app.core.logging import get_logger
from app.db.session import async_session_maker
from app.models.deterministic_evals import DeterministicEval
from app.models.run_telemetry import RunTelemetry
from app.services.control_plane import compute_deterministic_score
from app.services.deterministic_eval_queue import decode_deterministic_eval
from app.services.queue import QueuedTask

logger = get_logger(__name__)


async def execute_deterministic_eval(task: QueuedTask) -> None:
    """Evaluate one telemetry run and persist deterministic metrics."""
    payload = decode_deterministic_eval(task)
    async with async_session_maker() as session:
        run = await RunTelemetry.objects.by_id(payload.run_telemetry_id).first(session)
        if run is None:
            logger.warning(
                "deterministic_eval.execution.run_missing",
                extra={"run_telemetry_id": str(payload.run_telemetry_id)},
            )
            return

        existing = (
            await session.exec(
                select(DeterministicEval).where(
                    col(DeterministicEval.run_telemetry_id) == run.id,
                )
            )
        ).first()
        if existing is not None:
            logger.info(
                "deterministic_eval.execution.skip_existing",
                extra={"run_telemetry_id": str(run.id), "eval_id": str(existing.id)},
            )
            return

        computed = await compute_deterministic_score(session, run=run)
        row = DeterministicEval(
            run_telemetry_id=run.id,
            organization_id=run.organization_id,
            pack_id=run.pack_id,
            pack_key=run.pack_key,
            tier=run.tier,
            success_bool=run.success_bool,
            retries=run.retries,
            latency_regression_pct=computed.latency_regression_pct,
            format_contract_compliance=run.format_contract_passed,
            approval_gate_compliance=computed.approval_gate_compliance,
            score=computed.score,
            hard_regression=computed.hard_regression,
            details=computed.details,
        )
        session.add(row)
        await session.commit()
        logger.info(
            "deterministic_eval.execution.completed",
            extra={
                "run_telemetry_id": str(run.id),
                "score": computed.score,
                "hard_regression": computed.hard_regression,
            },
        )
