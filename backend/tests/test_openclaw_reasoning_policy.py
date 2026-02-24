# ruff: noqa: S101
"""Tests for OpenClaw reasoning mode selection policy."""

from __future__ import annotations

from app.services.openclaw.reasoning_policy import resolve_reasoning_mode


def test_resolve_reasoning_prefers_max_when_available() -> None:
    assert resolve_reasoning_mode(["off", "medium", "high", "max"], preferred="max") == "max"


def test_resolve_reasoning_uses_highest_supported_when_max_missing() -> None:
    assert resolve_reasoning_mode(["off", "medium", "high"], preferred="max") == "high"


def test_resolve_reasoning_falls_back_to_model_normal_behavior() -> None:
    assert resolve_reasoning_mode(["off", "normal"], preferred="max") == "normal"


def test_resolve_reasoning_returns_none_when_no_supported_modes() -> None:
    assert resolve_reasoning_mode([], preferred="max") is None


def test_resolve_reasoning_is_case_insensitive() -> None:
    assert resolve_reasoning_mode(["OFF", "MeDium", "HIGH"], preferred="MAX") == "high"
