"""Prompt evolution helper services (telemetry scaffolding + runtime selection)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import col, select

from app.core.logging import get_logger
from app.db.session import async_session_maker
from app.models.prompt_evolution import PromptPack, TaskEvalScore
from app.models.tasks import Task
from app.services.prompt_evolution_queue import QueuedPromptEvalTask, enqueue_prompt_eval_task

if False:  # pragma: no cover
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = get_logger(__name__)


async def record_task_completion_telemetry(
    session: AsyncSession,
    *,
    task: Task,
    previous_status: str,
) -> None:
    """Persist task-level evaluation telemetry when a task transitions to done.

    This is intentionally lightweight for phase-2 rollout: it records execution metadata
    and links to the active champion version when available. Dedicated evaluator workers
    can later enrich `score` and `passed` fields.
    """

    if task.board_id is None:
        return
    if task.status != "done" or previous_status == "done":
        return

    prompt_version_id = None
    pack = (
        await session.exec(
            select(PromptPack)
            .where(col(PromptPack.board_id) == task.board_id)
            .order_by(col(PromptPack.updated_at).desc())
            .limit(1),
        )
    ).first()
    if pack is not None:
        prompt_version_id = pack.champion_version_id

    telemetry = TaskEvalScore(
        board_id=task.board_id,
        task_id=task.id,
        prompt_version_id=prompt_version_id,
        evaluator_type="task_completion",
        detail_payload={
            "task_status": task.status,
            "previous_status": previous_status,
            "task_mode": task.task_mode,
            "auto_created": task.auto_created,
        },
    )
    session.add(telemetry)
    await session.flush()

    enqueue_prompt_eval_task(
        QueuedPromptEvalTask(
            eval_score_id=telemetry.id,
            queued_at=datetime.now(UTC),
        )
    )


async def process_prompt_eval_task(eval_score_id: object) -> None:
    """Background evaluator stub to compute deterministic baseline score."""

    async with async_session_maker() as session:
        eval_row = await session.get(TaskEvalScore, eval_score_id)
        if eval_row is None:
            return
        if eval_row.score is not None:
            return

        task = await session.get(Task, eval_row.task_id)
        if task is None:
            eval_row.score = 0.0
            eval_row.passed = False
            eval_row.detail_payload = {
                **eval_row.detail_payload,
                "error": "task_not_found",
            }
            session.add(eval_row)
            await session.commit()
            return

        title_len = len((task.title or "").strip())
        description_len = len((task.description or "").strip())
        score = 0.0
        if task.status == "done":
            score += 0.6
        if title_len >= 8:
            score += 0.2
        if description_len >= 20:
            score += 0.2

        eval_row.score = float(min(1.0, score))
        eval_row.passed = bool(eval_row.score >= 0.7)
        eval_row.detail_payload = {
            **eval_row.detail_payload,
            "title_len": title_len,
            "description_len": description_len,
            "scoring_version": "v0",
        }
        session.add(eval_row)
        await session.commit()
        logger.info(
            "prompt_evolution.eval.completed",
            extra={
                "eval_score_id": str(eval_row.id),
                "task_id": str(eval_row.task_id),
                "score": eval_row.score,
                "passed": eval_row.passed,
            },
        )
