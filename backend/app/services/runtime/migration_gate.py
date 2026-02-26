"""Migration-readiness gate for recovery scheduler startup."""

from __future__ import annotations

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import async_session_maker, get_alembic_head_revision

logger = get_logger(__name__)

_SCHEDULER_MIGRATION_READY = False
_CACHED_HEAD_REVISION: str | None = None


def reset_scheduler_migration_gate() -> None:
    """Reset in-process migration gate cache (test helper)."""
    global _SCHEDULER_MIGRATION_READY, _CACHED_HEAD_REVISION
    _SCHEDULER_MIGRATION_READY = False
    _CACHED_HEAD_REVISION = None


async def _fetch_current_migration_revision() -> str | None:
    async with async_session_maker() as session:
        result = await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
    raw = result.scalar_one_or_none()
    return str(raw) if raw is not None else None


async def is_scheduler_migration_ready() -> bool:
    """Return True only when DB revision matches local Alembic head."""
    global _SCHEDULER_MIGRATION_READY, _CACHED_HEAD_REVISION
    if _SCHEDULER_MIGRATION_READY:
        return True

    if _CACHED_HEAD_REVISION is None:
        _CACHED_HEAD_REVISION = get_alembic_head_revision()
    if not _CACHED_HEAD_REVISION:
        return False

    try:
        current_revision = await _fetch_current_migration_revision()
    except Exception as exc:  # pragma: no cover - defensive runtime path
        logger.warning("queue.worker.recovery_gate.check_failed", extra={"error": str(exc)})
        return False

    ready = current_revision == _CACHED_HEAD_REVISION
    if ready:
        _SCHEDULER_MIGRATION_READY = True
        logger.info(
            "queue.worker.recovery_gate.ready",
            extra={"head_revision": _CACHED_HEAD_REVISION},
        )
    return ready


__all__ = [
    "is_scheduler_migration_ready",
    "reset_scheduler_migration_gate",
]
