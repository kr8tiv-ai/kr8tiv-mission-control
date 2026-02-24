"""Queue helpers for prompt evolution evaluation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.services.queue import QueuedTask, enqueue_task, requeue_if_failed

TASK_TYPE = "prompt_eval_task"


@dataclass(frozen=True)
class QueuedPromptEvalTask:
    eval_score_id: UUID
    queued_at: datetime
    attempts: int = 0


def _task_from_payload(payload: QueuedPromptEvalTask) -> QueuedTask:
    return QueuedTask(
        task_type=TASK_TYPE,
        payload={
            "eval_score_id": str(payload.eval_score_id),
            "queued_at": payload.queued_at.isoformat(),
        },
        created_at=payload.queued_at,
        attempts=payload.attempts,
    )


def enqueue_prompt_eval_task(payload: QueuedPromptEvalTask) -> bool:
    return enqueue_task(
        _task_from_payload(payload),
        settings.rq_queue_name,
        redis_url=settings.rq_redis_url,
    )


def decode_prompt_eval_task(task: QueuedTask) -> QueuedPromptEvalTask:
    if task.task_type not in {TASK_TYPE, "legacy"}:
        raise ValueError(f"Unexpected task_type={task.task_type!r}; expected {TASK_TYPE!r}")
    payload: dict[str, Any] = task.payload
    queued_at = payload.get("queued_at") or payload.get("created_at")
    return QueuedPromptEvalTask(
        eval_score_id=UUID(payload["eval_score_id"]),
        queued_at=(
            datetime.fromisoformat(queued_at)
            if isinstance(queued_at, str)
            else datetime.now(UTC)
        ),
        attempts=int(payload.get("attempts", task.attempts)),
    )


def requeue_prompt_eval_task(task: QueuedTask, *, delay_seconds: float = 0) -> bool:
    return requeue_if_failed(
        task,
        settings.rq_queue_name,
        max_retries=settings.rq_dispatch_max_retries,
        redis_url=settings.rq_redis_url,
        delay_seconds=delay_seconds,
    )
