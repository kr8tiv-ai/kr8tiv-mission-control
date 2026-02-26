"""Channel ingress rollout policy and task event normalization."""

from __future__ import annotations

import hashlib
from typing import Any


def is_channel_enabled(*, channel: str, phase: str) -> bool:
    normalized_channel = (channel or "").strip().lower()
    normalized_phase = (phase or "").strip().lower()

    if normalized_channel == "telegram":
        return True
    if normalized_channel == "whatsapp":
        return normalized_phase in {"phase2", "ga"}
    return False


def is_owner_alert_channel_enabled(*, channel: str, phase: str) -> bool:
    """Gate owner-facing alert channels by rollout phase."""
    normalized_channel = (channel or "").strip().lower()
    if normalized_channel == "ui":
        return True
    return is_channel_enabled(channel=normalized_channel, phase=phase)


def build_ingress_task_event(
    *,
    channel: str,
    phase: str,
    message_id: str,
    chat_id: str,
    body: str,
) -> dict[str, Any]:
    """Create a normalized message->task payload with idempotency key."""
    if not is_channel_enabled(channel=channel, phase=phase):
        raise ValueError(f"Channel '{channel}' is not enabled for rollout phase '{phase}'.")

    key_source = f"{channel}:{chat_id}:{message_id}".encode("utf-8")
    idempotency_key = hashlib.sha256(key_source).hexdigest()
    return {
        "channel": channel,
        "chat_id": chat_id,
        "message_id": message_id,
        "body": body.strip(),
        "idempotency_key": idempotency_key,
    }
