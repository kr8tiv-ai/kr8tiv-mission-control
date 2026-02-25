"""Backup reminder cadence and policy evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.time import utcnow

REMINDER_INTERVAL = timedelta(days=3, hours=12)
BACKUP_WARNING = (
    "If you skip local backups, you can lose all your information. "
    "Choose a destination and confirm backup ownership."
)


@dataclass(frozen=True)
class ReminderEvaluation:
    """Computed reminder state for a backup policy."""

    reminder_due: bool
    next_prompt_at: datetime
    warning: str = BACKUP_WARNING
    cadence_per_week: int = 2


def evaluate_reminder(
    *,
    status: str,
    next_prompt_at: datetime | None,
    now: datetime | None = None,
) -> ReminderEvaluation:
    """Evaluate whether a backup reminder should be emitted for an organization."""
    current = now or utcnow()
    normalized_status = status.strip().lower() if status else "unconfirmed"
    if normalized_status == "confirmed" and next_prompt_at is not None and next_prompt_at > current:
        return ReminderEvaluation(reminder_due=False, next_prompt_at=next_prompt_at)

    if next_prompt_at is None or next_prompt_at <= current:
        return ReminderEvaluation(reminder_due=True, next_prompt_at=current + REMINDER_INTERVAL)

    return ReminderEvaluation(reminder_due=False, next_prompt_at=next_prompt_at)
