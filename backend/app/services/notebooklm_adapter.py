"""NotebookLM CLI adapter for mode-aware task orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings


class NotebookLMError(RuntimeError):
    """Raised when NotebookLM command execution fails."""


@dataclass(frozen=True)
class NotebookInfo:
    """Notebook identity details returned by create/list operations."""

    notebook_id: str
    share_url: str | None
    profile: str


@dataclass(frozen=True)
class NotebookSourcesPayload:
    """Notebook source payload used in create/ingestion flows."""

    urls: tuple[str, ...] = ()
    texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class NotebookQueryResult:
    """Normalized NotebookLM query result envelope."""

    answer: str
    conversation_id: str | None
    raw_ref: dict[str, object] | str
    error: str | None = None


def _profile_candidates(profile: str) -> tuple[str, ...]:
    if profile == "auto":
        return ("personal", "enterprise")
    return (profile,)


def _extract_json_payload(raw: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _as_text(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _extract_answer_and_conversation(
    payload: dict[str, object],
) -> tuple[str | None, str | None]:
    answer = _as_text(payload.get("answer")) or _as_text(payload.get("response"))
    conversation_id = _as_text(payload.get("conversation_id")) or _as_text(
        payload.get("conversationId")
    )
    nested = payload.get("value")
    if isinstance(nested, dict):
        answer = answer or _as_text(nested.get("answer")) or _as_text(nested.get("response"))
        conversation_id = conversation_id or _as_text(nested.get("conversation_id")) or _as_text(
            nested.get("conversationId")
        )
    return answer, conversation_id


def _normalize_error_message(exc: Exception) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        timeout_s = int(settings.notebooklm_timeout_seconds)
        return f"NotebookLM command timed out after {timeout_s}s"
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _append_query_audit_row(row: dict[str, object]) -> None:
    raw_path = settings.notebooklm_query_audit_log_path.strip()
    if not raw_path:
        return
    path = Path(raw_path)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[2] / raw_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


async def _run_command(args: list[str], *, profile: str) -> str:
    runner = shlex.split(settings.notebooklm_runner_cmd)
    cmd_with_profile = [*runner, *args, "--profile", profile]
    cmd_without_profile = [*runner, *args]
    env = dict(os.environ)
    env["NLM_PROFILES_DIR"] = settings.notebooklm_profiles_root

    def _invoke() -> str:
        def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=settings.notebooklm_timeout_seconds,
                env=env,
            )

        proc = _run(cmd_with_profile)
        if proc.returncode == 0:
            return proc.stdout.strip()

        message = proc.stderr.strip() or proc.stdout.strip() or "NotebookLM command failed"
        if "No such option: --profile" in message:
            fallback = _run(cmd_without_profile)
            if fallback.returncode == 0:
                return fallback.stdout.strip()
            fallback_message = (
                fallback.stderr.strip() or fallback.stdout.strip() or "NotebookLM command failed"
            )
            raise NotebookLMError(fallback_message)

        raise NotebookLMError(message)

    try:
        return await asyncio.to_thread(_invoke)
    except Exception as exc:  # pragma: no cover - depends on local CLI runtime
        raise NotebookLMError(_normalize_error_message(exc)) from exc


async def create_notebook(*, name: str, profile: str) -> NotebookInfo:
    """Create a notebook, trying fallback profiles when mode is auto."""
    last_error: Exception | None = None
    for candidate in _profile_candidates(profile):
        try:
            raw = await _run_command(["notebook", "create", "--name", name, "--json"], profile=candidate)
            payload = _extract_json_payload(raw) or {}
            notebook_id = _as_text(payload.get("id")) or _as_text(payload.get("notebook_id"))
            if not notebook_id:
                raise NotebookLMError("NotebookLM create did not return notebook_id")
            share_url = _as_text(payload.get("share_url")) or _as_text(payload.get("url"))
            return NotebookInfo(notebook_id=notebook_id, share_url=share_url, profile=candidate)
        except Exception as exc:  # pragma: no cover - depends on external CLI availability
            last_error = exc
            continue
    raise NotebookLMError(str(last_error or "NotebookLM create failed"))


async def add_sources(
    *,
    notebook_id: str,
    sources: NotebookSourcesPayload,
    profile: str,
) -> None:
    """Attach URL and text sources to a notebook."""
    last_error: Exception | None = None
    for candidate in _profile_candidates(profile):
        try:
            for url in sources.urls:
                await _run_command(
                    ["source", "add", "--notebook", notebook_id, "--url", url],
                    profile=candidate,
                )
            for text in sources.texts:
                await _run_command(
                    ["source", "add", "--notebook", notebook_id, "--text", text],
                    profile=candidate,
                )
            return
        except Exception as exc:  # pragma: no cover - depends on external CLI availability
            last_error = exc
            continue
    raise NotebookLMError(str(last_error or "NotebookLM source add failed"))


async def query_notebook(
    *,
    notebook_id: str,
    query: str,
    profile: str,
) -> NotebookQueryResult:
    """Run a NotebookLM query with automatic profile fallback when requested."""
    question_id = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    last_error: Exception | None = None
    for candidate in _profile_candidates(profile):
        try:
            raw = await _run_command(
                ["notebook", "query", notebook_id, query, "--json"],
                profile=candidate,
            )
            payload = _extract_json_payload(raw)
            if payload is None:
                result = NotebookQueryResult(
                    answer=raw,
                    conversation_id=None,
                    raw_ref=raw,
                )
                _append_query_audit_row(
                    {
                        "ts": datetime.now(UTC).isoformat(),
                        "profile": candidate,
                        "notebook_id": notebook_id,
                        "question_id": question_id,
                        "conversation_id": None,
                        "success": True,
                        "error": None,
                    }
                )
                return result
            answer, conversation_id = _extract_answer_and_conversation(payload)
            if answer:
                result = NotebookQueryResult(
                    answer=answer,
                    conversation_id=conversation_id,
                    raw_ref=payload,
                )
                _append_query_audit_row(
                    {
                        "ts": datetime.now(UTC).isoformat(),
                        "profile": candidate,
                        "notebook_id": notebook_id,
                        "question_id": question_id,
                        "conversation_id": conversation_id,
                        "success": True,
                        "error": None,
                    }
                )
                return result
            result = NotebookQueryResult(
                answer=raw,
                conversation_id=conversation_id,
                raw_ref=payload,
                error="missing_answer_field",
            )
            _append_query_audit_row(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "profile": candidate,
                    "notebook_id": notebook_id,
                    "question_id": question_id,
                    "conversation_id": conversation_id,
                    "success": True,
                    "error": "missing_answer_field",
                }
            )
            return result
        except Exception as exc:  # pragma: no cover - depends on external CLI availability
            normalized_error = _normalize_error_message(exc)
            _append_query_audit_row(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "profile": candidate,
                    "notebook_id": notebook_id,
                    "question_id": question_id,
                    "conversation_id": None,
                    "success": False,
                    "error": normalized_error,
                }
            )
            last_error = exc
            continue
    raise NotebookLMError(_normalize_error_message(last_error or Exception("NotebookLM query failed")))


async def check_notebook_access(*, profile: str) -> tuple[str, int]:
    """Probe notebook access for a profile, returning chosen profile and notebook count."""
    last_error: Exception | None = None
    for candidate in _profile_candidates(profile):
        try:
            raw = await _run_command(["notebook", "list", "--json"], profile=candidate)
            payload = _extract_json_payload(raw)
            if payload is None:
                return candidate, 0
            items = payload.get("items")
            if isinstance(items, list):
                return candidate, len(items)
            notebooks = payload.get("notebooks")
            if isinstance(notebooks, list):
                return candidate, len(notebooks)
            return candidate, 0
        except Exception as exc:  # pragma: no cover - depends on external CLI availability
            last_error = exc
            continue
    raise NotebookLMError(str(last_error or "NotebookLM capability check failed"))
