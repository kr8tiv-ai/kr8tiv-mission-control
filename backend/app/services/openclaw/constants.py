"""Shared constants for lifecycle orchestration services."""

from __future__ import annotations

import random
import re
from datetime import timedelta
from typing import Any

_GATEWAY_OPENCLAW_AGENT_PREFIX = "mc-gateway-"
_GATEWAY_AGENT_PREFIX = f"agent:{_GATEWAY_OPENCLAW_AGENT_PREFIX}"
_GATEWAY_AGENT_SUFFIX = ":main"

DEFAULT_HEARTBEAT_CONFIG: dict[str, Any] = {
    "every": "20m",
    "target": "last",
    "includeReasoning": False,
}

_HEARTBEAT_STALE_MULTIPLIER = 2
_HEARTBEAT_STALE_GRACE_SECONDS = 5 * 60
_MIN_OFFLINE_AFTER = timedelta(minutes=15)
_HEARTBEAT_EVERY_RE = re.compile(r"^\s*(?P<count>[1-9]\d*)\s*(?P<unit>[smhdw])\s*$", re.IGNORECASE)
_HEARTBEAT_UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
    "w": 60 * 60 * 24 * 7,
}


def _parse_heartbeat_every_to_seconds(value: str) -> int:
    match = _HEARTBEAT_EVERY_RE.match(value)
    if match is None:
        msg = "invalid heartbeat schedule format"
        raise ValueError(msg)
    count = int(match.group("count"))
    unit = match.group("unit").lower()
    return count * int(_HEARTBEAT_UNIT_SECONDS[unit])


def heartbeat_interval_seconds(heartbeat_config: object | None) -> int:
    """Return parsed heartbeat cadence seconds with a safe fallback."""
    fallback = _parse_heartbeat_every_to_seconds(str(DEFAULT_HEARTBEAT_CONFIG.get("every", "20m")))
    if not isinstance(heartbeat_config, dict):
        return fallback
    raw_every = heartbeat_config.get("every")
    if not isinstance(raw_every, str):
        return fallback
    try:
        return _parse_heartbeat_every_to_seconds(raw_every)
    except ValueError:
        return fallback


def stale_after_for_heartbeat_config(heartbeat_config: object | None) -> timedelta:
    """Derive stale/offline threshold from heartbeat cadence with jitter margin."""
    interval = heartbeat_interval_seconds(heartbeat_config)
    stale_after_seconds = interval * _HEARTBEAT_STALE_MULTIPLIER + _HEARTBEAT_STALE_GRACE_SECONDS
    stale_after = timedelta(seconds=stale_after_seconds)
    if stale_after < _MIN_OFFLINE_AFTER:
        return _MIN_OFFLINE_AFTER
    return stale_after


OFFLINE_AFTER = stale_after_for_heartbeat_config(DEFAULT_HEARTBEAT_CONFIG)
AGENT_SESSION_PREFIX = "agent"

DEFAULT_CHANNEL_HEARTBEAT_VISIBILITY: dict[str, bool] = {
    # Suppress routine HEARTBEAT_OK delivery by default.
    "showOk": False,
    "showAlerts": True,
    "useIndicator": True,
}

DEFAULT_IDENTITY_PROFILE = {
    "role": "Generalist",
    "communication_style": "direct, concise, practical",
    "emoji": ":gear:",
}

IDENTITY_PROFILE_FIELDS = {
    "role": "identity_role",
    "communication_style": "identity_communication_style",
    "emoji": "identity_emoji",
}

EXTRA_IDENTITY_PROFILE_FIELDS = {
    "autonomy_level": "identity_autonomy_level",
    "verbosity": "identity_verbosity",
    "output_format": "identity_output_format",
    "update_cadence": "identity_update_cadence",
    # Per-agent charter (optional).
    # Used to give agents a "purpose in life" and a distinct vibe.
    "purpose": "identity_purpose",
    "personality": "identity_personality",
    "custom_instructions": "identity_custom_instructions",
}

DEFAULT_GATEWAY_FILES = frozenset(
    {
        "AGENTS.md",
        "SOUL.md",
        "TOOLS.md",
        "IDENTITY.md",
        "USER.md",
        "HEARTBEAT.md",
        "MEMORY.md",
    },
)

# Lead-only workspace contract. Used for board leads to allow an iterative rollout
# without changing worker templates.
LEAD_GATEWAY_FILES = frozenset(
    {
        "AGENTS.md",
        "BOOTSTRAP.md",
        "IDENTITY.md",
        "SOUL.md",
        "USER.md",
        "MEMORY.md",
        "TOOLS.md",
        "HEARTBEAT.md",
    },
)

# These files are intended to evolve within the agent workspace.
# Provision them if missing, but avoid overwriting existing content during updates.
#
# Examples:
# - USER.md: human-provided context + lead intake notes
# - MEMORY.md: curated long-term memory (consolidated)
PRESERVE_AGENT_EDITABLE_FILES = frozenset({"USER.md", "MEMORY.md"})

HEARTBEAT_LEAD_TEMPLATE = "BOARD_HEARTBEAT.md.j2"
HEARTBEAT_AGENT_TEMPLATE = "BOARD_HEARTBEAT.md.j2"
SESSION_KEY_PARTS_MIN = 2
_SESSION_KEY_PARTS_MIN = SESSION_KEY_PARTS_MIN

MAIN_TEMPLATE_MAP = {
    "AGENTS.md": "BOARD_AGENTS.md.j2",
    "IDENTITY.md": "BOARD_IDENTITY.md.j2",
    "SOUL.md": "BOARD_SOUL.md.j2",
    "MEMORY.md": "BOARD_MEMORY.md.j2",
    "HEARTBEAT.md": "BOARD_HEARTBEAT.md.j2",
    "USER.md": "BOARD_USER.md.j2",
    "TOOLS.md": "BOARD_TOOLS.md.j2",
}

BOARD_SHARED_TEMPLATE_MAP = {
    "AGENTS.md": "BOARD_AGENTS.md.j2",
    "BOOTSTRAP.md": "BOARD_BOOTSTRAP.md.j2",
    "IDENTITY.md": "BOARD_IDENTITY.md.j2",
    "SOUL.md": "BOARD_SOUL.md.j2",
    "MEMORY.md": "BOARD_MEMORY.md.j2",
    "HEARTBEAT.md": "BOARD_HEARTBEAT.md.j2",
    "USER.md": "BOARD_USER.md.j2",
    "TOOLS.md": "BOARD_TOOLS.md.j2",
}

LEAD_TEMPLATE_MAP: dict[str, str] = {}

_TOOLS_KV_RE = re.compile(r"^(?P<key>[A-Z0-9_]+)=(?P<value>.*)$")
_NON_TRANSIENT_GATEWAY_ERROR_MARKERS = ("unsupported file",)
_TRANSIENT_GATEWAY_ERROR_MARKERS = (
    "connect call failed",
    "connection refused",
    "errno 111",
    "econnrefused",
    "did not receive a valid http response",
    "no route to host",
    "network is unreachable",
    "host is down",
    "name or service not known",
    "received 1012",
    "service restart",
    "http 503",
    "http 502",
    "http 504",
    "temporar",
    "timeout",
    "timed out",
    "connection closed",
    "connection reset",
)

_COORDINATION_GATEWAY_TIMEOUT_S = 45.0
_COORDINATION_GATEWAY_BASE_DELAY_S = 0.5
_COORDINATION_GATEWAY_MAX_DELAY_S = 5.0
_SECURE_RANDOM = random.SystemRandom()
