"""Webhook dispatch worker routines."""

from __future__ import annotations

import asyncio
import random
import time
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session_maker
from app.models.agents import Agent
from app.models.board_webhook_payloads import BoardWebhookPayload
from app.models.board_webhooks import BoardWebhook
from app.models.boards import Board
from app.services.channel_ingress import (
    evaluate_ingress_policy,
    ingress_policy_operator_note,
    is_owner_alert_channel_enabled,
)
from app.services.openclaw.gateway_dispatch import GatewayDispatchService
from app.services.queue import QueuedTask
from app.services.webhooks.queue import (
    QueuedInboundDelivery,
    decode_webhook_task,
    requeue_if_failed,
)

logger = get_logger(__name__)


def _build_payload_preview(payload_value: object) -> str:
    if isinstance(payload_value, str):
        return payload_value
    try:
        import json

        return json.dumps(payload_value, indent=2, ensure_ascii=True)
    except TypeError:
        return str(payload_value)


def _webhook_message(
    *,
    board: Board,
    webhook: BoardWebhook,
    payload: BoardWebhookPayload,
) -> str:
    preview = _build_payload_preview(payload.payload)
    policy = evaluate_ingress_policy(
        payload=payload.payload,
        headers=payload.headers,
        owner_user_id=settings.telegram_owner_user_id,
        bot_username=settings.telegram_bot_username,
        bot_user_id=settings.telegram_bot_user_id,
        allowed_agent_mentions=settings.allowed_arena_agent_ids(),
        allow_public_moderation=settings.telegram_allow_public_moderation,
        strict_dm_policy=settings.telegram_strict_dm_policy,
        require_owner_tag_or_reply=settings.telegram_require_owner_tag_or_reply,
        require_owner_for_task_direction=settings.telegram_require_owner_for_task_direction,
    )
    return (
        "WEBHOOK EVENT RECEIVED\n"
        f"Board: {board.name}\n"
        f"Webhook ID: {webhook.id}\n"
        f"Payload ID: {payload.id}\n"
        f"Instruction: {webhook.description}\n\n"
        f"{ingress_policy_operator_note(policy)}\n\n"
        "Take action:\n"
        "1) Triage this payload against the webhook instruction.\n"
        "2) If allow_task_direction=false, treat as discussion only and do NOT create/update tasks.\n"
        f"3) Otherwise reference payload ID {payload.id} in task descriptions for any task updates.\n\n"
        "Payload preview:\n"
        f"{preview}\n\n"
        "To inspect board memory entries:\n"
        f"GET /api/v1/agent/boards/{board.id}/memory?is_chat=false"
    )


async def _notify_target_agent(
    *,
    session: AsyncSession,
    board: Board,
    webhook: BoardWebhook,
    payload: BoardWebhookPayload,
) -> None:
    target_agent: Agent | None = None
    if webhook.agent_id is not None:
        target_agent = await Agent.objects.filter_by(id=webhook.agent_id, board_id=board.id).first(
            session
        )
    if target_agent is None:
        target_agent = await Agent.objects.filter_by(board_id=board.id, is_board_lead=True).first(
            session
        )
    if target_agent is None or not target_agent.openclaw_session_id:
        return

    dispatch = GatewayDispatchService(session)
    config = await dispatch.optional_gateway_config_for_board(board)
    if config is None:
        return

    message = _webhook_message(board=board, webhook=webhook, payload=payload)
    await dispatch.try_send_agent_message(
        session_key=target_agent.openclaw_session_id,
        config=config,
        agent_name=target_agent.name,
        message=message,
        deliver=False,
    )


async def _load_webhook_payload(
    *,
    session: AsyncSession,
    payload_id: UUID,
    webhook_id: UUID,
    board_id: UUID,
) -> tuple[Board, BoardWebhook, BoardWebhookPayload] | None:
    payload = await session.get(BoardWebhookPayload, payload_id)
    if payload is None:
        logger.warning(
            "webhook.queue.payload_missing",
            extra={
                "payload_id": str(payload_id),
                "webhook_id": str(webhook_id),
                "board_id": str(board_id),
            },
        )
        return None

    if payload.board_id != board_id or payload.webhook_id != webhook_id:
        logger.warning(
            "webhook.queue.payload_mismatch",
            extra={
                "payload_id": str(payload_id),
                "payload_webhook_id": str(payload.webhook_id),
                "payload_board_id": str(payload.board_id),
            },
        )
        return None

    board = await Board.objects.by_id(board_id).first(session)
    if board is None:
        logger.warning(
            "webhook.queue.board_missing",
            extra={"board_id": str(board_id), "payload_id": str(payload_id)},
        )
        return None

    webhook = await session.get(BoardWebhook, webhook_id)
    if webhook is None:
        logger.warning(
            "webhook.queue.webhook_missing",
            extra={"webhook_id": str(webhook_id), "board_id": str(board_id)},
        )
        return None

    if webhook.board_id != board_id:
        logger.warning(
            "webhook.queue.webhook_board_mismatch",
            extra={
                "webhook_id": str(webhook_id),
                "payload_board_id": str(payload.board_id),
                "expected_board_id": str(board_id),
            },
        )
        return None

    return board, webhook, payload


async def _process_single_item(item: QueuedInboundDelivery) -> None:
    async with async_session_maker() as session:
        loaded = await _load_webhook_payload(
            session=session,
            payload_id=item.payload_id,
            webhook_id=item.webhook_id,
            board_id=item.board_id,
        )
        if loaded is None:
            return

        board, webhook, payload = loaded
        await _notify_target_agent(session=session, board=board, webhook=webhook, payload=payload)
        await session.commit()


def _compute_webhook_retry_delay(attempts: int) -> float:
    base = float(settings.rq_dispatch_retry_base_seconds) * (2 ** max(0, attempts))
    return float(min(base, float(settings.rq_dispatch_retry_max_seconds)))


def _compute_webhook_retry_jitter(base_delay: float) -> float:
    upper_bound = float(
        min(float(settings.rq_dispatch_retry_max_seconds) / 10.0, float(base_delay) * 0.1)
    )
    return float(random.uniform(0.0, upper_bound))


async def process_webhook_queue_task(task: QueuedTask) -> None:
    item = decode_webhook_task(task)
    await _process_single_item(item)


def requeue_webhook_queue_task(task: QueuedTask, *, delay_seconds: float = 0) -> bool:
    payload = decode_webhook_task(task)
    return requeue_if_failed(payload, delay_seconds=delay_seconds)


async def flush_webhook_delivery_queue(*, block: bool = False, block_timeout: float = 0) -> int:
    """Consume queued webhook events and notify board leads in a throttled batch."""
    processed = 0
    while True:
        try:
            if block or block_timeout:
                item = dequeue_webhook_delivery(block=block, block_timeout=block_timeout)
            else:
                item = dequeue_webhook_delivery()
        except Exception:
            logger.exception("webhook.dispatch.dequeue_failed")
            continue

        if item is None:
            break

        try:
            await _process_single_item(item)
            processed += 1
            logger.info(
                "webhook.dispatch.success",
                extra={
                    "payload_id": str(item.payload_id),
                    "webhook_id": str(item.webhook_id),
                    "board_id": str(item.board_id),
                    "attempt": item.attempts,
                },
            )
        except Exception as exc:
            logger.exception(
                "webhook.dispatch.failed",
                extra={
                    "payload_id": str(item.payload_id),
                    "webhook_id": str(item.webhook_id),
                    "board_id": str(item.board_id),
                    "attempt": item.attempts,
                    "error": str(exc),
                    "owner_alert_telegram_enabled": is_owner_alert_channel_enabled(
                        channel="telegram",
                        phase=settings.channel_rollout_phase,
                    ),
                    "owner_alert_whatsapp_enabled": is_owner_alert_channel_enabled(
                        channel="whatsapp",
                        phase=settings.channel_rollout_phase,
                    ),
                },
            )
            delay = _compute_webhook_retry_delay(item.attempts)
            jitter = _compute_webhook_retry_jitter(delay)
            try:
                requeue_if_failed(item, delay_seconds=delay + jitter)
            except TypeError:
                requeue_if_failed(item)
        time.sleep(0.0)
        await asyncio.sleep(settings.rq_dispatch_throttle_seconds)
    if processed > 0:
        logger.info("webhook.dispatch.batch_complete", extra={"count": processed})
    return processed


def dequeue_webhook_delivery(
    *,
    block: bool = False,
    block_timeout: float = 0,
) -> QueuedInboundDelivery | None:
    """Pop one queued webhook delivery payload."""
    from app.services.queue import dequeue_task

    task = dequeue_task(
        settings.rq_queue_name,
        redis_url=settings.rq_redis_url,
        block=block,
        block_timeout=block_timeout,
    )
    if task is None:
        return None
    return decode_webhook_task(task)


def dequeue_webhook_delivery_task(
    *,
    block: bool = False,
    block_timeout: float = 0,
) -> QueuedInboundDelivery | None:
    """Backward-compatible alias for queue dequeue helper."""
    return dequeue_webhook_delivery(block=block, block_timeout=block_timeout)


def run_flush_webhook_delivery_queue() -> None:
    """RQ entrypoint for running the async queue flush from worker jobs."""
    logger.info(
        "webhook.dispatch.batch_started",
        extra={"throttle_seconds": settings.rq_dispatch_throttle_seconds},
    )
    start = time.time()
    asyncio.run(flush_webhook_delivery_queue())
    elapsed_ms = int((time.time() - start) * 1000)
    logger.info("webhook.dispatch.batch_finished", extra={"duration_ms": elapsed_ms})
