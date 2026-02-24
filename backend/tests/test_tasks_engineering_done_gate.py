from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import tasks as tasks_api
from app.api.deps import ActorContext
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.tasks import Task
from app.schemas.tasks import TaskUpdate


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


async def _seed_engineering_task(
    session: AsyncSession,
    *,
    arena_config: dict[str, object] | None,
) -> tuple[Task, Agent]:
    org_id = uuid4()
    board_id = uuid4()
    gateway_id = uuid4()
    agent_id = uuid4()

    session.add(Organization(id=org_id, name="org"))
    session.add(
        Gateway(
            id=gateway_id,
            organization_id=org_id,
            name="gateway",
            url="https://gateway.local",
            workspace_root="/tmp/workspace",
        )
    )
    session.add(
        Board(
            id=board_id,
            organization_id=org_id,
            name="board",
            slug="board",
            gateway_id=gateway_id,
            require_approval_for_done=False,
            require_review_before_done=False,
        )
    )
    agent = Agent(
        id=agent_id,
        name="worker",
        board_id=board_id,
        gateway_id=gateway_id,
        status="online",
    )
    task = Task(
        id=uuid4(),
        board_id=board_id,
        title="engineering task",
        status="review",
        task_mode="arena",
        assigned_agent_id=agent_id,
        arena_config=arena_config,
    )
    session.add(agent)
    session.add(task)
    await session.commit()
    return task, agent


@pytest.mark.asyncio
async def test_engineering_done_gate_blocks_done_without_required_checks() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            task, agent = await _seed_engineering_task(
                session,
                arena_config={
                    "done_gate_checks": {
                        "pr_created": True,
                        "ci_passed": False,
                        "human_reviewed": False,
                    }
                },
            )
            with pytest.raises(HTTPException) as exc:
                await tasks_api.update_task(
                    payload=TaskUpdate(status="done"),
                    task=task,
                    session=session,
                    actor=ActorContext(actor_type="agent", agent=agent),
                )
            assert exc.value.status_code == 409
            detail = exc.value.detail
            assert isinstance(detail, dict)
            assert detail["message"].startswith("Task cannot be marked done")
            assert set(detail["missing_checks"]) == {"ci_passed", "human_reviewed"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_engineering_done_gate_requires_ui_screenshot_when_ui_labeled() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            task, agent = await _seed_engineering_task(
                session,
                arena_config={
                    "ui_labeled": True,
                    "done_gate_checks": {
                        "pr_created": True,
                        "ci_passed": True,
                        "human_reviewed": True,
                        "ui_screenshot_present": False,
                    },
                },
            )
            with pytest.raises(HTTPException) as exc:
                await tasks_api.update_task(
                    payload=TaskUpdate(status="done"),
                    task=task,
                    session=session,
                    actor=ActorContext(actor_type="agent", agent=agent),
                )
            assert exc.value.status_code == 409
            detail = exc.value.detail
            assert isinstance(detail, dict)
            assert detail["missing_checks"] == ["ui_screenshot_present"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_engineering_done_gate_allows_done_with_required_checks() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            task, agent = await _seed_engineering_task(
                session,
                arena_config={
                    "ui_labeled": True,
                    "done_gate_checks": {
                        "pr_created": True,
                        "ci_passed": True,
                        "human_reviewed": True,
                        "ui_screenshot_present": True,
                    },
                },
            )
            updated = await tasks_api.update_task(
                payload=TaskUpdate(status="done"),
                task=task,
                session=session,
                actor=ActorContext(actor_type="agent", agent=agent),
            )
            assert updated.status == "done"
    finally:
        await engine.dispose()
