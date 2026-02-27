from __future__ import annotations

from pathlib import Path


def _heartbeat_template() -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "BOARD_HEARTBEAT.md.j2"
    )
    return path.read_text(encoding="utf-8")


def test_heartbeat_template_requires_probe_before_idle_ok() -> None:
    template = _heartbeat_template()

    assert "Pre-Flight Checks (Every Heartbeat)" in template
    assert "POST {{ base_url }}/api/v1/agent/heartbeat" in template
    assert "Return `HEARTBEAT_OK` only when:" in template
    assert "stay idle and return `HEARTBEAT_OK`" not in template

