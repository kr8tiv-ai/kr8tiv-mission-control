"""Task mode orchestration workers for notebook and arena flows."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlmodel import col, select

from app.core.config import settings
from app.core.logging import get_logger
from app.core.time import utcnow
from app.db.session import async_session_maker
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent
from app.models.boards import Board
from app.models.task_iterations import TaskIteration
from app.models.tasks import Task
from app.schemas.tasks import ArenaConfig, NotebookSources
from app.services.notebooklm_adapter import (
    NotebookInfo,
    NotebookLMError,
    NotebookSourcesPayload,
    add_sources,
    create_notebook,
    query_notebook,
)
from app.services.openclaw.gateway_dispatch import GatewayDispatchService
from app.services.openclaw.gateway_rpc import GatewayConfig, get_chat_history
from app.services.queue import QueuedTask
from app.services.supermemory_adapter import retrieve_arena_context_lines
from app.services.task_mode_queue import decode_task_mode_execution

logger = get_logger(__name__)
_VERDICT_PATTERN = re.compile(r"VERDICT:?\s*(APPROVED|REVISE)\s*$", re.IGNORECASE | re.MULTILINE)
_ARENA_MODES = {"arena", "arena_notebook"}
_NOTEBOOK_MODES = {"notebook", "arena_notebook", "notebook_creation"}


@dataclass(frozen=True)
class _ModeExecutionContext:
    board: Board
    task: Task
    gateway_config: GatewayConfig | None
    allowed_agents: tuple[str, ...]
    reviewer_agent: str


def _agent_aliases() -> dict[str, tuple[str, ...]]:
    return {
        "friday": ("friday", "claude"),
        "arsenal": ("arsenal", "codex", "gpt"),
        "edith": ("edith", "gemini"),
        "jocasta": ("jocasta", "kimi"),
    }


def _normalize_agent_id(raw: str) -> str:
    normalized = raw.strip().lower()
    for canonical, aliases in _agent_aliases().items():
        if normalized == canonical or normalized in aliases:
            return canonical
    return normalized


def _extract_verdict(text: str) -> str | None:
    match = _VERDICT_PATTERN.search(text)
    if match is None:
        return None
    return match.group(1).upper()


def _parse_sources(task: Task) -> NotebookSourcesPayload:
    config = task.arena_config or {}
    raw_sources = config.get("sources")
    if not isinstance(raw_sources, dict):
        return NotebookSourcesPayload()
    sources = NotebookSources.model_validate(raw_sources)
    return NotebookSourcesPayload(
        urls=tuple(sources.urls),
        texts=tuple(sources.texts),
    )


async def _load_supermemory_context(
    task: Task,
    *,
    board_id: UUID,
    limit: int = 3,
) -> list[str]:
    """Fetch compact context lines from Supermemory with graceful fallback."""
    query_parts = [task.title.strip()]
    if task.description:
        query_parts.append(task.description.strip())
    query = "\n".join(part for part in query_parts if part)

    try:
        return await retrieve_arena_context_lines(
            query=query,
            container_scope=str(board_id),
            limit=limit,
        )
    except Exception as exc:  # pragma: no cover - adapter degrades safely
        logger.warning(
            "task_mode.arena.supermemory.lookup_failed",
            extra={"task_id": str(task.id), "board_id": str(board_id), "error": str(exc)},
        )
        return []


def _select_arena_agents(config: ArenaConfig) -> list[str]:
    allowed = set(settings.allowed_arena_agent_ids())
    selected: list[str] = []
    for raw in config.agents:
        agent_id = _normalize_agent_id(raw)
        if agent_id in allowed and agent_id not in selected:
            selected.append(agent_id)
    if len(selected) > 4:
        selected = selected[:4]
    if not selected:
        selected = [settings.allowed_arena_agent_ids()[0]]
    reviewer = _normalize_agent_id(settings.arena_reviewer_agent)
    if reviewer in allowed and reviewer not in selected:
        selected.append(reviewer)
    return selected


async def _find_board_agent(
    board_id: UUID,
    agent_id: str,
) -> Agent | None:
    async with async_session_maker() as session:
        rows = list(
            await session.exec(
                select(Agent)
                .where(col(Agent.board_id) == board_id)
                .order_by(col(Agent.created_at).asc()),
            )
        )
    for row in rows:
        name_normalized = row.name.strip().lower()
        aliases = _agent_aliases().get(agent_id, (agent_id,))
        if any(alias in name_normalized for alias in aliases):
            return row
    return None


def _history_entries(history_payload: object) -> list[object]:
    if isinstance(history_payload, dict):
        for key in ("history", "messages", "items"):
            value = history_payload.get(key)
            if isinstance(value, list):
                return value
        return []
    if isinstance(history_payload, list):
        return history_payload
    return []


def _content_text(content: object) -> str | None:
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        message = content.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        nested = content.get("content")
        return _content_text(nested)
    if isinstance(content, list):
        for item in reversed(content):
            text = _content_text(item)
            if text:
                return text
    return None


def _latest_history_signature(history_payload: object) -> str | None:
    entries = _history_entries(history_payload)
    if not entries:
        return None
    latest = entries[-1]
    try:
        return json.dumps(latest, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(latest)


def _latest_history_role(history_payload: object) -> str | None:
    entries = _history_entries(history_payload)
    if entries and isinstance(entries[-1], dict):
        role = entries[-1].get("role")
        if isinstance(role, str):
            return role.strip().lower()
    if isinstance(history_payload, dict):
        role = history_payload.get("role")
        if isinstance(role, str):
            return role.strip().lower()
    return None


def _extract_latest_message(history_payload: object) -> str | None:
    entries = _history_entries(history_payload)
    if entries:
        for item in reversed(entries):
            text = _extract_latest_message(item)
            if text:
                return text

    if isinstance(history_payload, dict):
        role = history_payload.get("role")
        if isinstance(role, str) and role.strip().lower() not in ("assistant", "agent"):
            return None

        content_text = _content_text(history_payload.get("content"))
        if content_text:
            return content_text

        for key in ("output_text", "message", "text"):
            value = history_payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    if isinstance(history_payload, list):
        for item in reversed(history_payload):
            text = _extract_latest_message(item)
            if text:
                return text
        return None

    return None


async def _run_agent_turn(
    *,
    ctx: _ModeExecutionContext,
    agent_id: str,
    prompt: str,
    round_number: int,
    max_rounds: int,
    is_reviewer: bool,
) -> tuple[str, str]:
    import asyncio

    board_agent = await _find_board_agent(ctx.board.id, agent_id)
    if board_agent is None:
        raise RuntimeError(f"Arena agent '{agent_id}' unavailable: missing board agent")
    if not board_agent.openclaw_session_id:
        raise RuntimeError(f"Arena agent '{agent_id}' unavailable: missing session")
    if ctx.gateway_config is None:
        raise RuntimeError(f"Arena agent '{agent_id}' unavailable: missing gateway configuration")
    try:
        from app.services.openclaw.gateway_rpc import send_message

        # Capture baseline history signature before sending.
        history_before = await get_chat_history(
            board_agent.openclaw_session_id,
            config=ctx.gateway_config,
            limit=20,
        )
        baseline_signature = _latest_history_signature(history_before)

        await send_message(
            prompt,
            session_key=board_agent.openclaw_session_id,
            config=ctx.gateway_config,
            deliver=False,
        )

        # Poll for new response with exponential backoff (2s, 4s, 8s, 16s, 30s)
        backoff_delays = [2, 4, 8, 16, 30]  # ~60s total timeout
        for attempt, delay in enumerate(backoff_delays, start=1):
            await asyncio.sleep(delay)
            history = await get_chat_history(
                board_agent.openclaw_session_id,
                config=ctx.gateway_config,
                limit=20,
            )

            latest_role = _latest_history_role(history)
            current_signature = _latest_history_signature(history)
            response = _extract_latest_message(history)

            # A valid turn means a new latest history entry from assistant/agent with text.
            if (
                response
                and latest_role in {"assistant", "agent"}
                and current_signature is not None
                and current_signature != baseline_signature
            ):
                logger.info(
                    "task_mode.agent_turn.response_received",
                    extra={
                        "task_id": str(ctx.task.id),
                        "agent_id": agent_id,
                        "attempt": attempt,
                        "delay": delay,
                    },
                )
                return board_agent.name, response
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        logger.warning(
            "task_mode.agent_turn.gateway_failed",
            extra={
                "task_id": str(ctx.task.id),
                "agent_id": agent_id,
                "error": str(exc),
            },
        )
        detail = str(exc).strip() or exc.__class__.__name__
        raise RuntimeError(
            f"Arena agent '{agent_id}' unavailable: gateway response unavailable ({detail})"
        ) from exc
    raise RuntimeError(f"Arena agent '{agent_id}' unavailable: gateway response unavailable")


def _record_task_comment(session: Any, *, task_id: UUID, message: str) -> None:
    session.add(
        ActivityEvent(
            event_type="task.comment",
            task_id=task_id,
            message=message,
        )
    )


async def _ensure_notebook_for_task(task: Task) -> NotebookInfo:
    if task.notebook_id:
        return NotebookInfo(
            notebook_id=task.notebook_id,
            share_url=task.notebook_share_url,
            profile=task.notebook_profile,
        )
    notebook_name = task.title.strip() or f"Task {task.id}"
    info = await create_notebook(name=notebook_name, profile=task.notebook_profile)
    task.notebook_id = info.notebook_id
    task.notebook_share_url = info.share_url
    task.notebook_profile = info.profile
    return info


async def _execute_notebook_mode(session: Any, ctx: _ModeExecutionContext) -> None:
    task = ctx.task
    notebook_info = await _ensure_notebook_for_task(task)
    sources = _parse_sources(task)
    if sources.urls or sources.texts:
        await add_sources(
            notebook_id=notebook_info.notebook_id,
            sources=sources,
            profile=task.notebook_profile,
        )
    query = (task.description or task.title).strip()
    if query:
        answer = await query_notebook(
            notebook_id=notebook_info.notebook_id,
            query=query,
            profile=task.notebook_profile,
        )
        _record_task_comment(
            session,
            task_id=task.id,
            message=f"[NotebookLM] {answer}",
        )


async def _execute_notebook_creation_mode(ctx: _ModeExecutionContext) -> None:
    task = ctx.task
    notebook_info = await _ensure_notebook_for_task(task)
    sources = _parse_sources(task)
    if not (sources.urls or sources.texts):
        raise NotebookLMError("notebook_creation requires at least one source")
    await add_sources(
        notebook_id=notebook_info.notebook_id,
        sources=sources,
        profile=task.notebook_profile,
    )


async def _execute_arena_mode(
    session: Any,
    ctx: _ModeExecutionContext,
) -> None:
    task = ctx.task
    parsed_config = ArenaConfig.model_validate(task.arena_config or {})
    participants = _select_arena_agents(parsed_config)
    reviewer = _normalize_agent_id(ctx.reviewer_agent)
    final_agent = _normalize_agent_id(parsed_config.final_agent or participants[0])
    rounds = max(1, min(parsed_config.rounds, 10))

    if final_agent not in set(ctx.allowed_agents):
        final_agent = participants[0]

    # Pre-flight health check: verify all participants are available
    available_participants: list[str] = []
    for agent_id in participants:
        agent = await _find_board_agent(ctx.board.id, agent_id)
        if agent is None or not agent.openclaw_session_id:
            logger.warning(
                "task_mode.arena.agent_unavailable",
                extra={
                    "task_id": str(task.id),
                    "agent_id": agent_id,
                    "reason": "missing_agent" if agent is None else "missing_session_id",
                },
            )
            continue
        available_participants.append(agent_id)

    if not available_participants:
        raise RuntimeError(
            f"Arena execution failed: ALL agents unavailable. "
            f"Requested: {participants}, Available: none"
        )

    if len(available_participants) < len(participants):
        logger.warning(
            "task_mode.arena.partial_availability",
            extra={
                "task_id": str(task.id),
                "requested": participants,
                "available": available_participants,
            },
        )

    participants = available_participants

    summary_lines: list[str] = []

    # Supermemory integration
    if parsed_config.supermemory_enabled:
        context_lines = await _load_supermemory_context(task, board_id=ctx.board.id)
        if context_lines:
            summary_lines.append("Supermemory context:")
            for item in context_lines:
                summary_lines.append(f"- {item}")
            summary_lines.append("")

    summary_lines.append(f"Task: {task.title}")
    if task.description:
        summary_lines.append(f"Description: {task.description}")
    converged = False
    parse_error = False

    for round_number in range(1, rounds + 1):
        round_outputs: list[dict[str, object]] = []
        for agent_id in participants:
            prompt = "\n".join(summary_lines)
            display_name, output = await _run_agent_turn(
                ctx=ctx,
                agent_id=agent_id,
                prompt=prompt,
                round_number=round_number,
                max_rounds=rounds,
                is_reviewer=(agent_id == reviewer),
            )
            round_outputs.append(
                {
                    "agent_id": agent_id,
                    "display_name": display_name,
                    "output_text": output,
                }
            )
            summary_lines.append(f"[Round {round_number} | {agent_id}] {output}")

        # Truncate summary_lines if exceeding 8000 chars
        total_chars = sum(len(line) for line in summary_lines)
        if total_chars > 8000:
            # Keep header (task/description) and last 2 rounds only
            header_lines = [line for line in summary_lines if line.startswith("Task:") or line.startswith("Description:") or line.startswith("[Supermemory")]
            recent_rounds = [line for line in summary_lines if f"[Round {round_number}]" in line or f"[Round {round_number - 1}]" in line]
            summary_lines = header_lines + ["... (earlier rounds truncated) ..."] + recent_rounds

        reviewer_output = next(
            (
                str(item.get("output_text", ""))
                for item in round_outputs
                if item.get("agent_id") == reviewer
            ),
            "",
        )
        verdict = _extract_verdict(reviewer_output)
        if verdict is None:
            parse_error = True
            verdict = "ERROR"
        session.add(
            TaskIteration(
                task_id=task.id,
                round_number=round_number,
                agent_id=reviewer,
                output_text=reviewer_output or "Reviewer did not provide a verdict.",
                verdict=verdict,
                round_outputs=round_outputs,
            )
        )
        if verdict == "APPROVED":
            converged = True
            break
        if verdict == "ERROR":
            break

    if parse_error:
        raise RuntimeError("Arena reviewer did not return VERDICT: APPROVED or VERDICT: REVISE")

    if not converged:
        summary_lines.append(
            "WARNING: Arena convergence cap reached without APPROVED verdict. "
            "Proceeding with latest draft."
        )

    _final_name, final_output = await _run_agent_turn(
        ctx=ctx,
        agent_id=final_agent,
        prompt="\n".join(summary_lines),
        round_number=rounds,
        max_rounds=rounds,
        is_reviewer=False,
    )
    _record_task_comment(
        session,
        task_id=task.id,
        message=f"[Arena Final | {final_agent}] {final_output}",
    )

    if task.task_mode == "arena_notebook":
        notebook = await _ensure_notebook_for_task(task)
        await add_sources(
            notebook_id=notebook.notebook_id,
            sources=NotebookSourcesPayload(texts=(final_output,)),
            profile=task.notebook_profile,
        )


async def execute_task_mode(task: QueuedTask) -> None:
    """Execute one queued task-mode orchestration job."""
    payload = decode_task_mode_execution(task)
    async with async_session_maker() as session:
        board = (
            await session.exec(
                select(Board).where(col(Board.id) == payload.board_id),
            )
        ).first()
        if board is None:
            logger.warning(
                "task_mode.execution.board_missing",
                extra={"board_id": str(payload.board_id), "task_id": str(payload.task_id)},
            )
            return
        task_row = (
            await session.exec(
                select(Task)
                .where(col(Task.id) == payload.task_id)
                .where(col(Task.board_id) == payload.board_id),
            )
        ).first()
        if task_row is None:
            logger.warning(
                "task_mode.execution.task_missing",
                extra={"board_id": str(payload.board_id), "task_id": str(payload.task_id)},
            )
            return
        if task_row.task_mode == "standard":
            return

        dispatch = GatewayDispatchService(session)
        gateway_config = await dispatch.optional_gateway_config_for_board(board)
        ctx = _ModeExecutionContext(
            board=board,
            task=task_row,
            gateway_config=gateway_config,
            allowed_agents=settings.allowed_arena_agent_ids(),
            reviewer_agent=settings.arena_reviewer_agent,
        )

        task_row.status = "in_progress"
        task_row.updated_at = utcnow()
        session.add(task_row)
        await session.commit()

        try:
            if task_row.task_mode == "notebook":
                await _execute_notebook_mode(session, ctx)
            elif task_row.task_mode in _ARENA_MODES:
                await _execute_arena_mode(session, ctx)
            elif task_row.task_mode == "notebook_creation":
                await _execute_notebook_creation_mode(ctx)
            else:
                raise RuntimeError(f"Unsupported task_mode={task_row.task_mode!r}")
            task_row.status = "review"
            task_row.updated_at = utcnow()
            session.add(task_row)
            await session.commit()
        except Exception as exc:
            # Check if any iterations were completed
            iterations_count = (
                await session.exec(
                    select(TaskIteration).where(col(TaskIteration.task_id) == task_row.id)
                )
            ).all()
            # Only reset to inbox if zero iterations completed; otherwise keep in_progress
            if len(iterations_count) == 0:
                task_row.status = "inbox"
            # If iterations exist, leave status as in_progress so work isn't lost
            task_row.updated_at = utcnow()
            session.add(task_row)
            _record_task_comment(
                session,
                task_id=task_row.id,
                message=f"[Task Mode Error] {exc}",
            )
            await session.commit()
            raise
