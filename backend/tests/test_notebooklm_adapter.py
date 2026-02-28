# ruff: noqa: S101
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.services import notebooklm_adapter
from app.services.notebooklm_adapter import NotebookLMError


@pytest.mark.asyncio
async def test_run_command_appends_profile_to_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        _ = kwargs
        seen.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok":true}', stderr="")

    monkeypatch.setattr(notebooklm_adapter.settings, "notebooklm_runner_cmd", "nlm")
    monkeypatch.setattr(notebooklm_adapter, "subprocess", notebooklm_adapter.subprocess)
    monkeypatch.setattr(notebooklm_adapter.subprocess, "run", _fake_run)

    output = await notebooklm_adapter._run_command(
        ["notebook", "query", "nb-1", "hello", "--json"],
        profile="default",
    )

    assert output == '{"ok":true}'
    assert seen == [["nlm", "notebook", "query", "nb-1", "hello", "--json", "--profile", "default"]]


@pytest.mark.asyncio
async def test_run_command_retries_without_profile_when_cli_rejects_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        _ = kwargs
        seen.append(list(cmd))
        if len(seen) == 1:
            return subprocess.CompletedProcess(
                cmd,
                2,
                stdout="",
                stderr="No such option: --profile",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok":true}', stderr="")

    monkeypatch.setattr(notebooklm_adapter.settings, "notebooklm_runner_cmd", "nlm")
    monkeypatch.setattr(notebooklm_adapter, "subprocess", notebooklm_adapter.subprocess)
    monkeypatch.setattr(notebooklm_adapter.subprocess, "run", _fake_run)

    output = await notebooklm_adapter._run_command(
        ["notebook", "query", "nb-2", "hello", "--json"],
        profile="default",
    )

    assert output == '{"ok":true}'
    assert seen == [
        ["nlm", "notebook", "query", "nb-2", "hello", "--json", "--profile", "default"],
        ["nlm", "notebook", "query", "nb-2", "hello", "--json"],
    ]


@pytest.mark.asyncio
async def test_query_notebook_uses_positional_cli_contract_and_parses_nested_answer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen: dict[str, object] = {}

    async def _fake_run_command(args: list[str], *, profile: str) -> str:
        seen["args"] = args
        seen["profile"] = profile
        return '{"value":{"answer":"nested answer","conversation_id":"conv-1"}}'

    monkeypatch.setattr(notebooklm_adapter, "_run_command", _fake_run_command)
    monkeypatch.setattr(
        notebooklm_adapter.settings,
        "notebooklm_query_audit_log_path",
        str(tmp_path / "query-audit.jsonl"),
    )

    result = await notebooklm_adapter.query_notebook(
        notebook_id="nb-1",
        query="what changed?",
        profile="personal",
    )

    assert seen["args"] == ["notebook", "query", "nb-1", "what changed?", "--json"]
    assert seen["profile"] == "personal"
    assert result.answer == "nested answer"
    assert result.conversation_id == "conv-1"


@pytest.mark.asyncio
async def test_query_notebook_returns_raw_text_when_json_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def _fake_run_command(args: list[str], *, profile: str) -> str:
        _ = args, profile
        return "plain output"

    monkeypatch.setattr(notebooklm_adapter, "_run_command", _fake_run_command)
    monkeypatch.setattr(
        notebooklm_adapter.settings,
        "notebooklm_query_audit_log_path",
        str(tmp_path / "query-audit.jsonl"),
    )

    result = await notebooklm_adapter.query_notebook(
        notebook_id="nb-2",
        query="hello",
        profile="personal",
    )

    assert result.answer == "plain output"
    assert result.conversation_id is None
    assert result.error is None


@pytest.mark.asyncio
async def test_query_notebook_raises_when_all_profiles_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def _failing_run_command(args: list[str], *, profile: str) -> str:
        _ = args, profile
        raise NotebookLMError("Authentication expired")

    monkeypatch.setattr(notebooklm_adapter, "_run_command", _failing_run_command)
    monkeypatch.setattr(
        notebooklm_adapter.settings,
        "notebooklm_query_audit_log_path",
        str(tmp_path / "query-audit.jsonl"),
    )

    with pytest.raises(NotebookLMError, match="Authentication expired"):
        await notebooklm_adapter.query_notebook(
            notebook_id="nb-3",
            query="hello",
            profile="auto",
        )
