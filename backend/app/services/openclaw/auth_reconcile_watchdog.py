"""Automatic Mission Control -> gateway auth reconcile trigger for repeated agent 401s."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable

from sqlmodel import select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session_maker
from app.models.gateways import Gateway
from app.services.openclaw.provisioning_db import GatewayTemplateSyncOptions, OpenClawProvisioningService

logger = get_logger(__name__)

_AGENT_PATH_PREFIX = "/api/v1/agent/"
_failure_timestamps: deque[float] = deque()
_last_trigger_at: float = 0.0
_reconcile_in_flight = False


def _now_monotonic() -> float:
    return time.monotonic()


def _enabled() -> bool:
    return bool(getattr(settings, "auth_reconcile_on_401_enabled", True))


def _threshold() -> int:
    return max(1, int(getattr(settings, "auth_reconcile_401_threshold", 3)))


def _window_seconds() -> int:
    return max(1, int(getattr(settings, "auth_reconcile_401_window_seconds", 120)))


def _cooldown_seconds() -> int:
    return max(1, int(getattr(settings, "auth_reconcile_cooldown_seconds", 300)))


def _schedule_reconcile_task(coro: Awaitable[None]) -> None:
    asyncio.get_running_loop().create_task(coro)


def _is_agent_api_path(path: str) -> bool:
    normalized = str(path or "").strip().lower()
    return normalized.startswith(_AGENT_PATH_PREFIX)


def _prune_old_failures(*, now: float) -> None:
    window = float(_window_seconds())
    while _failure_timestamps and (now - _failure_timestamps[0]) > window:
        _failure_timestamps.popleft()


def record_401_failure(*, path: str) -> None:
    """Record an agent 401 and auto-trigger reconcile when threshold/cooldown permits."""
    global _last_trigger_at

    if not _enabled() or not _is_agent_api_path(path):
        return

    now = _now_monotonic()
    _prune_old_failures(now=now)
    _failure_timestamps.append(now)

    if len(_failure_timestamps) < _threshold():
        return
    if _reconcile_in_flight:
        return
    if _last_trigger_at > 0 and (now - _last_trigger_at) < float(_cooldown_seconds()):
        return

    _last_trigger_at = now
    try:
        _schedule_reconcile_task(_run_reconcile_once())
        logger.warning(
            "agent auth reconcile trigger path=%s failures_window=%s threshold=%s",
            path,
            len(_failure_timestamps),
            _threshold(),
        )
    except RuntimeError:
        # No running loop in current context; periodic timer remains fallback.
        logger.warning("agent auth reconcile trigger skipped: no running event loop")


async def _run_reconcile_once() -> None:
    global _reconcile_in_flight
    if _reconcile_in_flight:
        return
    _reconcile_in_flight = True
    try:
        async with async_session_maker() as session:
            gateways = (await session.exec(select(Gateway))).all()
            if not gateways:
                logger.warning("agent auth reconcile skipped: no gateways configured")
                return

            service = OpenClawProvisioningService(session)
            options = GatewayTemplateSyncOptions(
                user=None,
                include_main=True,
                lead_only=False,
                reset_sessions=True,
                rotate_tokens=True,
                force_bootstrap=False,
                overwrite=True,
                board_id=None,
            )
            success = 0
            for gateway in gateways:
                result = await service.sync_gateway_templates(gateway, options)
                if not result.errors:
                    success += 1
                else:
                    logger.warning(
                        "agent auth reconcile gateway errors gateway_id=%s errors=%s",
                        gateway.id,
                        len(result.errors),
                    )
            await session.commit()
            logger.warning(
                "agent auth reconcile completed gateways=%s success=%s",
                len(gateways),
                success,
            )
    except Exception as exc:
        logger.exception("agent auth reconcile failed: %s", exc)
    finally:
        _reconcile_in_flight = False


def reset_state_for_tests() -> None:
    """Reset in-memory watchdog state for deterministic tests."""
    global _last_trigger_at, _reconcile_in_flight
    _failure_timestamps.clear()
    _last_trigger_at = 0.0
    _reconcile_in_flight = False
