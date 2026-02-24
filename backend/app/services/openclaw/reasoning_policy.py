"""Reasoning mode resolution for model/runtime capabilities."""

from __future__ import annotations

from collections.abc import Iterable

_REASONING_PRIORITY = ("max", "high", "medium", "low")


def _normalized_modes(supported_modes: Iterable[str] | None) -> list[str]:
    if not supported_modes:
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in supported_modes:
        mode = str(raw).strip().lower()
        if not mode or mode in seen:
            continue
        seen.add(mode)
        normalized.append(mode)
    return normalized


def resolve_reasoning_mode(
    supported_modes: Iterable[str] | None,
    *,
    preferred: str = "max",
) -> str | None:
    """Resolve best reasoning mode: preferred -> highest tier -> normal/default."""
    modes = _normalized_modes(supported_modes)
    if not modes:
        return None

    preferred_mode = str(preferred).strip().lower()
    if preferred_mode and preferred_mode in modes:
        return preferred_mode

    for candidate in _REASONING_PRIORITY:
        if candidate in modes:
            return candidate

    if "normal" in modes:
        return "normal"

    return modes[0]
