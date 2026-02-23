"""NotebookLM CLI adapter for mode-aware task orchestration."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
from dataclasses import dataclass

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


async def _run_command(args: list[str], *, profile: str) -> str:
    cmd = [*shlex.split(settings.notebooklm_runner_cmd), "--profile", profile, *args]
    env = dict(os.environ)
    env["NLM_PROFILES_DIR"] = settings.notebooklm_profiles_root

    def _invoke() -> str:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=settings.notebooklm_timeout_seconds,
            env=env,
        )
        if proc.returncode != 0:
            raise NotebookLMError(proc.stderr.strip() or proc.stdout.strip() or "NotebookLM command failed")
        return proc.stdout.strip()

    return await asyncio.to_thread(_invoke)


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


async def query_notebook(*, notebook_id: str, query: str, profile: str) -> str:
    """Run a NotebookLM query with automatic profile fallback when requested."""
    last_error: Exception | None = None
    for candidate in _profile_candidates(profile):
        try:
            raw = await _run_command(
                ["notebook", "query", "--notebook", notebook_id, "--query", query, "--json"],
                profile=candidate,
            )
            payload = _extract_json_payload(raw)
            if payload is None:
                return raw
            answer = _as_text(payload.get("answer")) or _as_text(payload.get("response"))
            if answer:
                return answer
            return raw
        except Exception as exc:  # pragma: no cover - depends on external CLI availability
            last_error = exc
            continue
    raise NotebookLMError(str(last_error or "NotebookLM query failed"))
