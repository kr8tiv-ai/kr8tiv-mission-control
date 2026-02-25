"""Queue helpers for deterministic run-telemetry evaluation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.services.queue import QueuedTask, enqueue_task, requeue_if_failed

logger = get_logger(__name__)
TASK_TYPE = "deterministic_eval"


@dataclass(frozen=True)
class QueuedDeterministicEval:
    """Payload envelope for deterministic evaluation background jobs."""

    run_telemetry_id: UUID
    queued_at: datetime
    attempts: int = 0


def _task_from_payload(payload: QueuedDeterministicEval) -> QueuedTask:
    return QueuedTask(
        task_type=TASK_TYPE,
        payload={
            "run_telemetry_id": str(payload.run_telemetry_id),
            "queued_at": payload.queued_at.isoformat(),
        },
        created_at=payload.queued_at,
        attempts=payload.attempts,
    )


def decode_deterministic_eval(task: QueuedTask) -> QueuedDeterministicEval:
    """Decode generic queued task into deterministic evaluation payload."""
    if task.task_type not in {TASK_TYPE, "legacy"}:
        raise ValueError(f"Unexpected task_type={task.task_type!r}; expected {TASK_TYPE!r}")
    payload: dict[str, Any] = task.payload
    queued_at = payload.get("queued_at") or payload.get("created_at")
    return QueuedDeterministicEval(
        run_telemetry_id=UUID(payload["run_telemetry_id"]),
        queued_at=(
            datetime.fromisoformat(queued_at) if isinstance(queued_at, str) else datetime.now(UTC)
        ),
        attempts=int(payload.get("attempts", task.attempts)),
    )


def enqueue_deterministic_eval(payload: QueuedDeterministicEval) -> bool:
    """Enqueue deterministic evaluation for one run telemetry row."""
    try:
        enqueue_task(_task_from_payload(payload), settings.rq_queue_name, redis_url=settings.rq_redis_url)
        logger.info(
            "deterministic_eval.queue.enqueued",
            extra={
                "run_telemetry_id": str(payload.run_telemetry_id),
                "attempt": payload.attempts,
            },
        )
        return True
    except Exception as exc:
        logger.warning(
            "deterministic_eval.queue.enqueue_failed",
            extra={
                "run_telemetry_id": str(payload.run_telemetry_id),
                "error": str(exc),
            },
        )
        return False


def requeue_deterministic_eval(task: QueuedTask, *, delay_seconds: float = 0) -> bool:
    """Requeue failed deterministic eval jobs with capped retry policy."""
    return requeue_if_failed(
        task,
        settings.rq_queue_name,
        max_retries=settings.rq_dispatch_max_retries,
        redis_url=settings.rq_redis_url,
        delay_seconds=delay_seconds,
    )
