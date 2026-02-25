from __future__ import annotations

from app.services.openclaw.reasoning_policy import resolve_reasoning_mode


def test_resolve_reasoning_prefers_max_then_highest_then_default() -> None:
    assert resolve_reasoning_mode(["off", "medium", "high"], preferred="max") == "high"
    assert resolve_reasoning_mode(["off", "normal"], preferred="max") == "normal"
    assert resolve_reasoning_mode([], preferred="max") == "normal"


def test_resolve_reasoning_uses_requested_mode_when_supported() -> None:
    assert resolve_reasoning_mode(["off", "normal", "high"], preferred="high") == "high"


def test_resolve_reasoning_normalizes_aliases() -> None:
    assert resolve_reasoning_mode(["default", "low"], preferred="max") == "normal"
