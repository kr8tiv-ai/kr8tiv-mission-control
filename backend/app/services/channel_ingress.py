"""Channel ingress rollout policy and task event normalization."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

_TELEGRAM_CHAT_KEYS = ("message", "edited_message", "channel_post", "edited_channel_post")
_MENTION_RE = re.compile(r"@(?P<handle>[A-Za-z0-9_]{2,64})")
_TASK_DIRECTIVE_RE = re.compile(
    r"(?i)\b("
    r"create\s+task|open\s+task|assign\s+task|update\s+task|"
    r"execute\s+trade|place\s+order|buy\s+\w+|sell\s+\w+|"
    r"start\s+sniper|deploy\s+\w+|run\s+this"
    r")\b",
)
_PROMPT_INJECTION_RE = re.compile(
    r"(?i)\b("
    r"ignore\s+(all|any|previous|prior)\s+(instructions|system|rules)|"
    r"reveal\s+(system|developer)\s+prompt|"
    r"bypass\s+(guardrails|safety)|"
    r"override\s+(policy|rules)|"
    r"exfiltrat(e|ion)\s+(token|secret|key)"
    r")\b",
)


@dataclass(frozen=True, slots=True)
class IngressPolicyDecision:
    channel: str
    sender_id: str | None
    chat_type: str | None
    is_owner: bool
    is_private_chat: bool
    is_public_chat: bool
    addressed_to_runtime: bool
    allow_processing: bool
    allow_task_direction: bool
    task_directive_detected: bool
    prompt_injection_detected: bool
    blocked_reason: str | None


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _normalized_sender_id(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def infer_ingress_channel(
    *,
    payload: object,
    headers: dict[str, str] | None = None,
    channel: str | None = None,
) -> str:
    explicit = (channel or "").strip().lower()
    if explicit:
        return explicit

    normalized_headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    header_channel = (
        normalized_headers.get("x-ingress-channel")
        or normalized_headers.get("x-channel")
        or normalized_headers.get("x-source-channel")
        or ""
    ).strip().lower()
    if header_channel:
        return header_channel

    payload_map = _as_dict(payload)
    payload_channel = str(payload_map.get("channel", "")).strip().lower()
    if payload_channel:
        return payload_channel

    if payload_map.get("update_id") is not None:
        return "telegram"
    if any(key in payload_map for key in _TELEGRAM_CHAT_KEYS):
        return "telegram"
    return "unknown"


def _telegram_message_payload(payload: object) -> dict[str, object]:
    payload_map = _as_dict(payload)
    nested = _as_dict(payload_map.get("payload")) or _as_dict(payload_map.get("data"))
    candidate = nested if nested else payload_map

    for key in _TELEGRAM_CHAT_KEYS:
        message = _as_dict(candidate.get(key))
        if message:
            return message

    callback = _as_dict(candidate.get("callback_query"))
    if callback:
        callback_message = _as_dict(callback.get("message"))
        if callback_message:
            if "from" not in callback_message:
                sender = _as_dict(callback.get("from"))
                if sender:
                    callback_message["from"] = sender
            if "text" not in callback_message:
                callback_data = callback.get("data")
                if isinstance(callback_data, str) and callback_data.strip():
                    callback_message["text"] = callback_data
            return callback_message

    if "chat" in candidate and "from" in candidate:
        return candidate
    return {}


def _telegram_text(message: dict[str, object]) -> str:
    for key in ("text", "caption"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _entity_mentions(text: str, message: dict[str, object]) -> set[str]:
    handles = {match.group("handle").lower() for match in _MENTION_RE.finditer(text)}
    entities = message.get("entities")
    if not isinstance(entities, list):
        entities = message.get("caption_entities")
    if not isinstance(entities, list):
        return handles
    for entity in entities:
        entity_map = _as_dict(entity)
        if str(entity_map.get("type", "")).lower() != "mention":
            continue
        offset = entity_map.get("offset")
        length = entity_map.get("length")
        if not isinstance(offset, int) or not isinstance(length, int) or length <= 1:
            continue
        token = text[offset : offset + length].strip()
        if token.startswith("@") and len(token) > 1:
            handles.add(token[1:].lower())
    return handles


def evaluate_ingress_policy(
    *,
    payload: object,
    headers: dict[str, str] | None = None,
    channel: str | None = None,
    owner_user_id: str = "",
    bot_username: str = "",
    bot_user_id: str = "",
    allowed_agent_mentions: tuple[str, ...] = (),
    allow_public_moderation: bool = True,
    strict_dm_policy: bool = True,
    require_owner_tag_or_reply: bool = True,
    require_owner_for_task_direction: bool = True,
) -> IngressPolicyDecision:
    resolved_channel = infer_ingress_channel(payload=payload, headers=headers, channel=channel)
    if resolved_channel != "telegram":
        return IngressPolicyDecision(
            channel=resolved_channel,
            sender_id=None,
            chat_type=None,
            is_owner=False,
            is_private_chat=False,
            is_public_chat=False,
            addressed_to_runtime=True,
            allow_processing=True,
            allow_task_direction=True,
            task_directive_detected=False,
            prompt_injection_detected=False,
            blocked_reason=None,
        )

    message = _telegram_message_payload(payload)
    sender_id = _normalized_sender_id(_as_dict(message.get("from")).get("id"))
    owner_id = _normalized_sender_id(owner_user_id)
    is_owner = bool(owner_id and sender_id and owner_id == sender_id)
    chat_type = str(_as_dict(message.get("chat")).get("type", "")).strip().lower() or None
    is_private_chat = chat_type == "private"
    is_public_chat = chat_type in {"group", "supergroup", "channel"}
    text = _telegram_text(message)
    mentions = _entity_mentions(text, message)

    normalized_bot_username = bot_username.strip().lstrip("@").lower()
    allowed_mentions = {mention.strip().lstrip("@").lower() for mention in allowed_agent_mentions}
    addressed_by_mention = bool(
        mentions
        and (
            (normalized_bot_username and normalized_bot_username in mentions)
            or bool(mentions.intersection(allowed_mentions))
        )
    )

    reply_to = _as_dict(message.get("reply_to_message"))
    reply_from = _as_dict(reply_to.get("from"))
    reply_user_id = _normalized_sender_id(reply_from.get("id"))
    reply_username = str(reply_from.get("username", "")).strip().lstrip("@").lower()
    normalized_bot_user_id = _normalized_sender_id(bot_user_id)
    addressed_by_reply = bool(
        reply_to
        and (
            (normalized_bot_username and reply_username == normalized_bot_username)
            or (normalized_bot_user_id and reply_user_id == normalized_bot_user_id)
        )
    )
    addressed_to_runtime = addressed_by_mention or addressed_by_reply

    task_directive_detected = bool(_TASK_DIRECTIVE_RE.search(text))
    prompt_injection_detected = bool(_PROMPT_INJECTION_RE.search(text))

    allow_processing = True
    allow_task_direction = True
    blocked_reason: str | None = None

    if is_private_chat and strict_dm_policy and not is_owner:
        allow_processing = False
        allow_task_direction = False
        blocked_reason = "telegram_dm_not_owner"
    elif is_public_chat and not is_owner and not allow_public_moderation:
        allow_processing = False
        allow_task_direction = False
        blocked_reason = "telegram_public_moderation_disabled"
    elif is_public_chat and is_owner and require_owner_tag_or_reply and not addressed_to_runtime:
        allow_processing = False
        allow_task_direction = False
        blocked_reason = "telegram_owner_not_addressed"

    if prompt_injection_detected and not is_owner:
        allow_task_direction = False
        if blocked_reason is None:
            blocked_reason = "prompt_injection_detected"
    if task_directive_detected and require_owner_for_task_direction and not is_owner:
        allow_task_direction = False
        if blocked_reason is None:
            blocked_reason = "task_direction_non_owner"

    return IngressPolicyDecision(
        channel=resolved_channel,
        sender_id=sender_id,
        chat_type=chat_type,
        is_owner=is_owner,
        is_private_chat=is_private_chat,
        is_public_chat=is_public_chat,
        addressed_to_runtime=addressed_to_runtime,
        allow_processing=allow_processing,
        allow_task_direction=allow_task_direction,
        task_directive_detected=task_directive_detected,
        prompt_injection_detected=prompt_injection_detected,
        blocked_reason=blocked_reason,
    )


def ingress_policy_tags(decision: IngressPolicyDecision) -> list[str]:
    tags = [f"ingress:{decision.channel}"]
    if decision.is_private_chat:
        tags.append("ingress:dm")
    elif decision.is_public_chat:
        tags.append("ingress:public")
    if decision.is_owner:
        tags.append("ingress:owner")
    else:
        tags.append("ingress:non_owner")
    if not decision.allow_processing:
        tags.append("policy:blocked")
    if not decision.allow_task_direction:
        tags.append("policy:no_task_direction")
    if decision.prompt_injection_detected:
        tags.append("policy:prompt_injection")
    if decision.blocked_reason:
        tags.append(f"policy:{decision.blocked_reason}")
    return tags


def ingress_policy_operator_note(decision: IngressPolicyDecision) -> str:
    lines = [
        "Ingress policy summary:",
        f"- channel={decision.channel} chat_type={decision.chat_type or 'unknown'} sender={decision.sender_id or 'unknown'}",
        f"- allow_processing={decision.allow_processing} allow_task_direction={decision.allow_task_direction}",
    ]
    if decision.blocked_reason:
        lines.append(f"- blocked_reason={decision.blocked_reason}")
    if decision.prompt_injection_detected:
        lines.append("- prompt_injection_detected=true")
    return "\n".join(lines)


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
