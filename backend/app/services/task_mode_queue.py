"""Queue helpers for task mode execution jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.services.channel_ingress import build_ingress_task_event
from app.services.queue import QueuedTask, enqueue_task, requeue_if_failed

logger = get_logger(__name__)
TASK_TYPE = "task_mode_execution"


@dataclass(frozen=True)
class QueuedTaskModeExecution:
    """Payload envelope for asynchronous task mode orchestration."""

    board_id: UUID
    task_id: UUID
    queued_at: datetime
    attempts: int = 0


def _task_from_payload(payload: QueuedTaskModeExecution) -> QueuedTask:
    return QueuedTask(
        task_type=TASK_TYPE,
        payload={
            "board_id": str(payload.board_id),
            "task_id": str(payload.task_id),
            "queued_at": payload.queued_at.isoformat(),
        },
        created_at=payload.queued_at,
        attempts=payload.attempts,
    )


def decode_task_mode_execution(task: QueuedTask) -> QueuedTaskModeExecution:
    """Decode a generic queued task into a task-mode execution envelope."""
    if task.task_type not in {TASK_TYPE, "legacy"}:
        raise ValueError(f"Unexpected task_type={task.task_type!r}; expected {TASK_TYPE!r}")
    payload: dict[str, Any] = task.payload
    queued_at = payload.get("queued_at") or payload.get("created_at")
    return QueuedTaskModeExecution(
        board_id=UUID(payload["board_id"]),
        task_id=UUID(payload["task_id"]),
        queued_at=(
            datetime.fromisoformat(queued_at)
            if isinstance(queued_at, str)
            else datetime.now(UTC)
        ),
        attempts=int(payload.get("attempts", task.attempts)),
    )


def enqueue_task_mode_execution(payload: QueuedTaskModeExecution) -> bool:
    """Enqueue a task-mode orchestration request."""
    try:
        queued = _task_from_payload(payload)
        enqueue_task(queued, settings.rq_queue_name, redis_url=settings.rq_redis_url)
        logger.info(
            "task_mode.queue.enqueued",
            extra={
                "board_id": str(payload.board_id),
                "task_id": str(payload.task_id),
                "attempt": payload.attempts,
            },
        )
        return True
    except Exception as exc:
        logger.warning(
            "task_mode.queue.enqueue_failed",
            extra={
                "board_id": str(payload.board_id),
                "task_id": str(payload.task_id),
                "error": str(exc),
            },
        )
        return False


def requeue_task_mode_execution(
    task: QueuedTask,
    *,
    delay_seconds: float = 0,
) -> bool:
    """Requeue a failed task-mode orchestration job with capped retries."""
    return requeue_if_failed(
        task,
        settings.rq_queue_name,
        max_retries=settings.rq_dispatch_max_retries,
        redis_url=settings.rq_redis_url,
        delay_seconds=delay_seconds,
    )


def is_skill_route_eligible(skill_metadata: dict[str, Any] | None) -> bool:
    """Return whether a skill passed ingest validation and can be routed."""
    # Backward compatibility: skills created before ingest metadata was introduced
    # remain installable unless they are explicitly marked as non-accepted.
    if not isinstance(skill_metadata, dict):
        return True

    ingest_status = str(skill_metadata.get("ingest_status", "")).strip().lower()
    if not ingest_status:
        return True
    return ingest_status == "accepted"


def normalize_channel_event(
    *,
    channel: str,
    message_id: str,
    chat_id: str,
    body: str,
) -> dict[str, Any]:
    """Normalize inbound channel payload into a queue-safe task event contract."""
    return build_ingress_task_event(
        channel=channel,
        phase=settings.channel_rollout_phase,
        message_id=message_id,
        chat_id=chat_id,
        body=body,
    )
