"""Reasoning mode resolution helpers for OpenClaw runtime defaults."""

from __future__ import annotations

from typing import Iterable

_PREFERRED_REASONING = "max"
_DEFAULT_REASONING = "normal"
_RANKED_REASONING_MODES = (
    "max",
    "high",
    "medium",
    "normal",
    "low",
    "minimal",
    "off",
)
_ALIAS_MAP = {
    "default": _DEFAULT_REASONING,
    "standard": _DEFAULT_REASONING,
    "on": _DEFAULT_REASONING,
    "none": "off",
}


def _normalize_mode(mode: object) -> str:
    if not isinstance(mode, str):
        return ""
    normalized = mode.strip().lower()
    if not normalized:
        return ""
    return _ALIAS_MAP.get(normalized, normalized)


def _normalized_unique_modes(modes: Iterable[object] | None) -> list[str]:
    if not modes:
        return []
    unique: list[str] = []
    for raw_mode in modes:
        normalized = _normalize_mode(raw_mode)
        if not normalized or normalized in unique:
            continue
        unique.append(normalized)
    return unique


def resolve_reasoning_mode(
    supported: Iterable[object] | None,
    preferred: str = _PREFERRED_REASONING,
) -> str:
    """Resolve the best available reasoning mode.

    Policy:
    1. Use preferred mode when available.
    2. When preferred is `max`, fall back to the highest supported tier.
    3. If no supported tiers are known, use model default (`normal`).
    """

    normalized_supported = _normalized_unique_modes(supported)
    normalized_preferred = _normalize_mode(preferred) or _PREFERRED_REASONING

    if not normalized_supported:
        if normalized_preferred == _PREFERRED_REASONING:
            return _DEFAULT_REASONING
        return normalized_preferred

    if normalized_preferred in normalized_supported:
        return normalized_preferred

    if normalized_preferred == _PREFERRED_REASONING:
        for candidate in _RANKED_REASONING_MODES:
            if candidate in normalized_supported:
                return candidate
        for candidate in normalized_supported:
            if candidate not in {"off"}:
                return candidate
        return normalized_supported[0]

    for candidate in _RANKED_REASONING_MODES:
        if candidate in normalized_supported:
            return candidate
    return normalized_supported[0]
