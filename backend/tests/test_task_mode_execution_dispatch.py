# ruff: noqa: S101
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.activity_events import ActivityEvent
from app.models.boards import Board
from app.models.organizations import Organization
from app.models.task_iterations import TaskIteration
from app.models.tasks import Task
from app.services import task_mode_execution
from app.services.queue import QueuedTask


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _seed_board_and_task(
    session: AsyncSession,
    *,
    task_mode: str,
    status: str = "inbox",
) -> tuple[Board, Task]:
    org = Organization(id=uuid4(), name="KR8TIV")
    board = Board(
        id=uuid4(),
        organization_id=org.id,
        name="Mission Control",
        slug="mission-control",
        description="Test board",
    )
    task = Task(
        id=uuid4(),
        board_id=board.id,
        title=f"Task {task_mode}",
        description="Dispatch test",
        status=status,
        task_mode=task_mode,
        arena_config={"agents": ["arsenal"], "rounds": 1, "final_agent": "arsenal"},
    )
    session.add(org)
    session.add(board)
    session.add(task)
    await session.commit()
    return board, task


def _queued_task(board_id, task_id) -> QueuedTask:
    return QueuedTask(
        task_type="task_mode_execution",
        payload={
            "board_id": str(board_id),
            "task_id": str(task_id),
            "queued_at": datetime.now(UTC).isoformat(),
        },
        created_at=datetime.now(UTC),
        attempts=0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_call"),
    [
        ("notebook", "notebook"),
        ("arena", "arena"),
        ("arena_notebook", "arena"),
        ("notebook_creation", "notebook_creation"),
    ],
)
async def test_execute_task_mode_dispatches_supported_modes_and_sets_review(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_call: str,
) -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    called: list[str] = []

    async with session_maker() as session:
        board, task = await _seed_board_and_task(session, task_mode=mode)

    monkeypatch.setattr(task_mode_execution, "async_session_maker", session_maker)

    async def _fake_notebook(_session, _ctx):
        called.append("notebook")

    async def _fake_arena(_session, _ctx):
        called.append("arena")

    async def _fake_notebook_creation(_ctx):
        called.append("notebook_creation")

    monkeypatch.setattr(task_mode_execution, "_execute_notebook_mode", _fake_notebook)
    monkeypatch.setattr(task_mode_execution, "_execute_arena_mode", _fake_arena)
    monkeypatch.setattr(task_mode_execution, "_execute_notebook_creation_mode", _fake_notebook_creation)

    await task_mode_execution.execute_task_mode(_queued_task(board.id, task.id))

    assert called == [expected_call]
    async with session_maker() as session:
        persisted = await session.get(Task, task.id)
        assert persisted is not None
        assert persisted.status == "review"

    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_task_mode_standard_is_noop() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        board, task = await _seed_board_and_task(session, task_mode="standard", status="inbox")

    from app.services import task_mode_execution as module
    from pytest import MonkeyPatch

    monkeypatch = MonkeyPatch()
    monkeypatch.setattr(module, "async_session_maker", session_maker)
    try:
        await module.execute_task_mode(_queued_task(board.id, task.id))
    finally:
        monkeypatch.undo()

    async with session_maker() as session:
        persisted = await session.get(Task, task.id)
        assert persisted is not None
        assert persisted.status == "inbox"

    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_task_mode_unsupported_mode_resets_to_inbox_and_comments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        board, task = await _seed_board_and_task(session, task_mode="unknown_mode")

    monkeypatch.setattr(task_mode_execution, "async_session_maker", session_maker)

    with pytest.raises(RuntimeError, match="Unsupported task_mode"):
        await task_mode_execution.execute_task_mode(_queued_task(board.id, task.id))

    async with session_maker() as session:
        persisted = await session.get(Task, task.id)
        assert persisted is not None
        assert persisted.status == "inbox"
        comments = (
            await session.exec(
                select(ActivityEvent)
                .where(col(ActivityEvent.task_id) == task.id)
                .where(col(ActivityEvent.event_type) == "task.comment"),
            )
        ).all()
        assert comments
        assert comments[-1].message is not None
        assert "[Task Mode Error]" in comments[-1].message

    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_task_mode_failure_with_iterations_keeps_in_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        board, task = await _seed_board_and_task(session, task_mode="arena")
        session.add(
            TaskIteration(
                id=uuid4(),
                task_id=task.id,
                round_number=1,
                agent_id="arsenal",
                output_text="draft",
                verdict="REVISE",
                round_outputs=[],
            )
        )
        await session.commit()

    monkeypatch.setattr(task_mode_execution, "async_session_maker", session_maker)

    async def _failing_arena(_session, _ctx):
        raise RuntimeError("arena failed")

    monkeypatch.setattr(task_mode_execution, "_execute_arena_mode", _failing_arena)

    with pytest.raises(RuntimeError, match="arena failed"):
        await task_mode_execution.execute_task_mode(_queued_task(board.id, task.id))

    async with session_maker() as session:
        persisted = await session.get(Task, task.id)
        assert persisted is not None
        assert persisted.status == "in_progress"

    await engine.dispose()
