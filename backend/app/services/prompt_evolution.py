"""Prompt evolution helper services (telemetry scaffolding + runtime selection)."""

from __future__ import annotations

from sqlmodel import col, select

from app.models.prompt_evolution import PromptPack, TaskEvalScore
from app.models.tasks import Task

if False:  # pragma: no cover
    from sqlmodel.ext.asyncio.session import AsyncSession


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
