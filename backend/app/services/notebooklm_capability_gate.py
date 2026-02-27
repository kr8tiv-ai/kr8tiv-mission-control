"""Runtime capability gate for NotebookLM-backed task operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.core.config import settings
from app.core.time import utcnow
from app.services.notebooklm_adapter import NotebookLMError, check_notebook_access

NotebookCapabilityState = Literal["ready", "retryable", "misconfig", "hard_fail"]
_SUPPORTED_PROFILES = {"auto", "personal", "enterprise", "default"}


@dataclass(frozen=True, slots=True)
class NotebookCapabilityGateResult:
    state: NotebookCapabilityState
    reason: str
    operator_message: str
    checked_at: datetime
    selected_profile: str | None = None
    notebook_count: int | None = None


def _result(
    *,
    state: NotebookCapabilityState,
    reason: str,
    operator_message: str,
    selected_profile: str | None = None,
    notebook_count: int | None = None,
) -> NotebookCapabilityGateResult:
    return NotebookCapabilityGateResult(
        state=state,
        reason=reason,
        operator_message=operator_message,
        checked_at=utcnow(),
        selected_profile=selected_profile,
        notebook_count=notebook_count,
    )


def _classify_probe_error(message: str) -> tuple[NotebookCapabilityState, str, str]:
    lowered = message.lower()

    if any(marker in lowered for marker in ("403", "forbidden", "suspended", "disabled")):
        return "hard_fail", "forbidden", "NotebookLM account access forbidden. Lane halted."

    if any(
        marker in lowered
        for marker in (
            "no such file",
            "not found",
            "invalid profile",
            "profiles",
            "cookies",
            "runner command",
        )
    ):
        return "misconfig", "profile_missing", "NotebookLM profile/runner misconfigured."

    if any(marker in lowered for marker in ("auth", "401", "expired", "csrf")):
        return "retryable", "auth_expired", "NotebookLM auth expired. Run `nlm login`."

    if any(
        marker in lowered
        for marker in (
            "timeout",
            "timed out",
            "temporarily",
            "503",
            "429",
            "rate limit",
            "connection",
            "network",
            "unavailable",
        )
    ):
        return "retryable", "transient_error", "NotebookLM temporary failure. Retry with backoff."

    return "retryable", "unknown_error", "NotebookLM capability probe failed. Retry advised."


async def evaluate_notebooklm_capability(
    *,
    profile: str,
    notebook_id: str | None = None,
    require_notebook: bool = False,
) -> NotebookCapabilityGateResult:
    """Evaluate whether NotebookLM operations are safe to execute right now."""
    normalized_profile = profile.strip().lower()
    if normalized_profile not in _SUPPORTED_PROFILES:
        return _result(
            state="misconfig",
            reason="invalid_profile",
            operator_message=f"Invalid notebook profile '{profile}'.",
        )

    if not settings.notebooklm_runner_cmd.strip():
        return _result(
            state="misconfig",
            reason="runner_missing",
            operator_message="NotebookLM runner command is not configured.",
        )

    if settings.notebooklm_timeout_seconds <= 0:
        return _result(
            state="misconfig",
            reason="timeout_invalid",
            operator_message="NotebookLM timeout must be greater than zero.",
        )

    if require_notebook and not (notebook_id or "").strip():
        return _result(
            state="misconfig",
            reason="missing_notebook_id",
            operator_message="NotebookLM task requires a notebook id.",
        )

    try:
        selected_profile, notebook_count = await check_notebook_access(profile=normalized_profile)
    except NotebookLMError as exc:
        state, reason, operator_message = _classify_probe_error(str(exc))
        return _result(state=state, reason=reason, operator_message=operator_message)

    return _result(
        state="ready",
        reason="ok",
        operator_message="NotebookLM capability gate passed.",
        selected_profile=selected_profile,
        notebook_count=notebook_count,
    )

