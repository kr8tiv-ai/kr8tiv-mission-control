"""Generic queue worker with task-type dispatch."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.config import settings
from app.db.session import async_session_maker
from app.core.logging import get_logger
from app.services.deterministic_eval_execution import execute_deterministic_eval
from app.services.deterministic_eval_queue import TASK_TYPE as DETERMINISTIC_EVAL_TASK_TYPE
from app.services.deterministic_eval_queue import requeue_deterministic_eval
from app.services.queue import QueuedTask, dequeue_task
from app.services.runtime.migration_gate import is_scheduler_migration_ready
from app.services.runtime.recovery_scheduler import RecoveryScheduler
from app.services.task_mode_execution import execute_task_mode
from app.services.task_mode_queue import (
    TASK_TYPE as TASK_MODE_TASK_TYPE,
)
from app.services.task_mode_queue import (
    requeue_task_mode_execution,
)
from app.services.webhooks.dispatch import (
    process_webhook_queue_task,
    requeue_webhook_queue_task,
)
from app.services.webhooks.queue import TASK_TYPE as WEBHOOK_TASK_TYPE

logger = get_logger(__name__)


@dataclass(frozen=True)
class _TaskHandler:
    handler: Callable[[QueuedTask], Awaitable[None]]
    attempts_to_delay: Callable[[int], float]
    requeue: Callable[[QueuedTask, float], bool]


_TASK_HANDLERS: dict[str, _TaskHandler] = {
    WEBHOOK_TASK_TYPE: _TaskHandler(
        handler=process_webhook_queue_task,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_webhook_queue_task(task, delay_seconds=delay),
    ),
    # task mode handler defined below
    TASK_MODE_TASK_TYPE: _TaskHandler(
        handler=execute_task_mode,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_task_mode_execution(task, delay_seconds=delay),
    ),
    DETERMINISTIC_EVAL_TASK_TYPE: _TaskHandler(
        handler=execute_deterministic_eval,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_deterministic_eval(task, delay_seconds=delay),
    ),
}


def _compute_jitter(base_delay: float) -> float:
    return random.uniform(0, min(settings.rq_dispatch_retry_max_seconds / 10, base_delay * 0.1))


async def flush_queue(*, block: bool = False, block_timeout: float = 0) -> int:
    """Consume one queue batch and dispatch by task type."""
    processed = 0
    while True:
        try:
            task = dequeue_task(
                settings.rq_queue_name,
                redis_url=settings.rq_redis_url,
                block=block,
                block_timeout=block_timeout,
            )
        except Exception:
            logger.exception(
                "queue.worker.dequeue_failed",
                extra={"queue_name": settings.rq_queue_name},
            )
            continue

        if task is None:
            break

        handler = _TASK_HANDLERS.get(task.task_type)
        if handler is None:
            logger.warning(
                "queue.worker.task_unhandled",
                extra={
                    "task_type": task.task_type,
                    "queue_name": settings.rq_queue_name,
                },
            )
            continue

        try:
            await handler.handler(task)
            processed += 1
            logger.info(
                "queue.worker.success",
                extra={
                    "task_type": task.task_type,
                    "attempt": task.attempts,
                },
            )
        except Exception as exc:
            logger.exception(
                "queue.worker.failed",
                extra={
                    "task_type": task.task_type,
                    "attempt": task.attempts,
                    "error": str(exc),
                },
            )
            base_delay = handler.attempts_to_delay(task.attempts)
            delay = base_delay + _compute_jitter(base_delay)
            if not handler.requeue(task, delay):
                logger.warning(
                    "queue.worker.drop_task",
                    extra={
                        "task_type": task.task_type,
                        "attempt": task.attempts,
                    },
                )
        await asyncio.sleep(settings.rq_dispatch_throttle_seconds)

    if processed > 0:
        logger.info("queue.worker.batch_complete", extra={"count": processed})
    return processed


async def run_recovery_scheduler_once() -> bool:
    """Run one periodic recovery sweep when runtime setting enables it."""
    if not settings.recovery_loop_enabled:
        return False

    if not await is_scheduler_migration_ready():
        logger.info("queue.worker.recovery_sweep_deferred_migrations_pending")
        return False

    async with async_session_maker() as session:
        result = await RecoveryScheduler(session=session).run_once()
    logger.info(
        "queue.worker.recovery_sweep",
        extra={
            "board_count": result.board_count,
            "incident_count": result.incident_count,
            "alerts_sent": result.alerts_sent,
            "alerts_suppressed_dedupe": result.alerts_suppressed_dedupe,
            "alerts_skipped_status": result.alerts_skipped_status,
        },
    )
    return True


async def _run_worker_loop() -> None:
    next_recovery_due_at = time.monotonic()
    while True:
        try:
            now = time.monotonic()
            if settings.recovery_loop_enabled and now >= next_recovery_due_at:
                await run_recovery_scheduler_once()
                next_recovery_due_at = time.monotonic() + max(
                    int(settings.recovery_loop_interval_seconds),
                    1,
                )
            await flush_queue(
                block=True,
                block_timeout=1,
            )
        except Exception:
            logger.exception(
                "queue.worker.loop_failed",
                extra={"queue_name": settings.rq_queue_name},
            )
            await asyncio.sleep(1)


def run_worker() -> None:
    """RQ entrypoint for running continuous queue processing."""
    logger.info(
        "queue.worker.batch_started",
        extra={"throttle_seconds": settings.rq_dispatch_throttle_seconds},
    )
    try:
        asyncio.run(_run_worker_loop())
    finally:
        logger.info("queue.worker.stopped", extra={"queue_name": settings.rq_queue_name})


if __name__ == "__main__":  # pragma: no cover - module entrypoint
    run_worker()
