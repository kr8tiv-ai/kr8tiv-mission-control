# ruff: noqa: S101
from __future__ import annotations

import json

from app.cli import control_plane_status


def test_build_status_url_encodes_optional_params() -> None:
    url = control_plane_status.build_status_url(
        base_url="http://localhost:8100/",
        board_id="11111111-1111-1111-1111-111111111111",
        profile="enterprise",
    )
    assert (
        url
        == "http://localhost:8100/api/v1/runtime/ops/control-plane-status"
        "?board_id=11111111-1111-1111-1111-111111111111&profile=enterprise"
    )


def test_fetch_control_plane_status_sends_bearer_token(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class _FakeResponse:
        status = 200

        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

    def _fake_urlopen(req, timeout: int):  # noqa: ANN001
        seen["url"] = req.full_url
        seen["authorization"] = req.headers.get("Authorization")
        seen["timeout"] = timeout
        return _FakeResponse({"ok": True, "arena": {"healthy": True}})

    monkeypatch.setattr(control_plane_status.request, "urlopen", _fake_urlopen)

    payload = control_plane_status.fetch_control_plane_status(
        base_url="http://localhost:8100",
        token="test-token",
        board_id=None,
        profile="auto",
        timeout_seconds=9,
    )

    assert seen["url"] == "http://localhost:8100/api/v1/runtime/ops/control-plane-status?profile=auto"
    assert seen["authorization"] == "Bearer test-token"
    assert seen["timeout"] == 9
    assert payload["ok"] is True


def test_main_prints_json_payload(monkeypatch, capsys) -> None:
    def _fake_fetch(**_kwargs):  # noqa: ANN001
        return {"checked_at": "2026-02-27T00:00:00Z", "arena": {"healthy": True}}

    monkeypatch.setattr(control_plane_status, "fetch_control_plane_status", _fake_fetch)

    exit_code = control_plane_status.main(
        [
            "--base-url",
            "http://localhost:8100",
            "--token",
            "abc123",
            "--profile",
            "auto",
        ]
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "\"checked_at\"" in output
    assert "\"arena\"" in output
