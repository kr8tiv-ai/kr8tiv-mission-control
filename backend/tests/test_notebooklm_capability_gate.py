from __future__ import annotations

import pytest

from app.services import notebooklm_capability_gate
from app.services.notebooklm_adapter import NotebookLMError


@pytest.mark.asyncio
async def test_gate_rejects_invalid_profile() -> None:
    result = await notebooklm_capability_gate.evaluate_notebooklm_capability(
        profile="invalid-profile",
    )

    assert result.state == "misconfig"
    assert result.reason == "invalid_profile"


@pytest.mark.asyncio
async def test_gate_requires_notebook_id_when_requested() -> None:
    result = await notebooklm_capability_gate.evaluate_notebooklm_capability(
        profile="auto",
        notebook_id="",
        require_notebook=True,
    )

    assert result.state == "misconfig"
    assert result.reason == "missing_notebook_id"


@pytest.mark.asyncio
async def test_gate_ready_when_probe_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_check_access(*, profile: str) -> tuple[str, int]:
        assert profile == "auto"
        return "personal", 3

    monkeypatch.setattr(notebooklm_capability_gate, "check_notebook_access", _fake_check_access)
    result = await notebooklm_capability_gate.evaluate_notebooklm_capability(profile="auto")

    assert result.state == "ready"
    assert result.reason == "ok"
    assert result.selected_profile == "personal"


@pytest.mark.asyncio
async def test_gate_classifies_retryable_auth_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_probe(*, profile: str) -> tuple[str, int]:
        _ = profile
        raise NotebookLMError("Authentication expired. Run 'nlm login' in your terminal.")

    monkeypatch.setattr(notebooklm_capability_gate, "check_notebook_access", _failing_probe)
    result = await notebooklm_capability_gate.evaluate_notebooklm_capability(profile="auto")

    assert result.state == "retryable"
    assert result.reason == "auth_expired"


@pytest.mark.asyncio
async def test_gate_classifies_hard_fail_for_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_probe(*, profile: str) -> tuple[str, int]:
        _ = profile
        raise NotebookLMError("403 Forbidden: account suspended")

    monkeypatch.setattr(notebooklm_capability_gate, "check_notebook_access", _failing_probe)
    result = await notebooklm_capability_gate.evaluate_notebooklm_capability(profile="auto")

    assert result.state == "hard_fail"
    assert result.reason == "forbidden"


@pytest.mark.asyncio
async def test_gate_classifies_misconfig_for_missing_profile_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_probe(*, profile: str) -> tuple[str, int]:
        _ = profile
        raise NotebookLMError("No such file or directory: /var/lib/notebooklm/profiles")

    monkeypatch.setattr(notebooklm_capability_gate, "check_notebook_access", _failing_probe)
    result = await notebooklm_capability_gate.evaluate_notebooklm_capability(profile="auto")

    assert result.state == "misconfig"
    assert result.reason == "profile_missing"
