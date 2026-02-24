from __future__ import annotations

from app.services.channel_ingress import is_channel_enabled


def test_whatsapp_disabled_until_phase2_gate() -> None:
    assert is_channel_enabled(channel="telegram", phase="phase1") is True
    assert is_channel_enabled(channel="whatsapp", phase="phase1") is False


def test_whatsapp_enabled_in_phase2() -> None:
    assert is_channel_enabled(channel="whatsapp", phase="phase2") is True
