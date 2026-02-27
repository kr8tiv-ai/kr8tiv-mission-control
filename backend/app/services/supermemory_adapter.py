"""Supermemory retrieval adapter with tenant-scoped defaults and graceful fallback."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_container_tag(*, prefix: str, scope: str) -> str:
    """Build a scoped container tag used to isolate tenant retrieval context."""
    return f"{prefix}:{scope}"


def _extract_text_candidates(payload: dict[str, object]) -> list[str]:
    source = (
        payload.get("results")
        or payload.get("hits")
        or payload.get("items")
        or payload.get("data")
        or []
    )
    if not isinstance(source, Sequence) or isinstance(source, (str, bytes, bytearray)):
        return []
    lines: list[str] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        maybe_text = item.get("content") or item.get("text") or item.get("snippet")
        if isinstance(maybe_text, str) and maybe_text.strip():
            lines.append(" ".join(maybe_text.strip().split()))
    return lines


class SupermemoryAdapter:
    """Bounded Supermemory retrieval helper for task-mode arena contexts."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        top_k: int | None = None,
        threshold: float | None = None,
        timeout_seconds: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.supermemory_base_url).rstrip("/")
        self.api_key = (api_key if api_key is not None else settings.supermemory_api_key).strip()
        self.top_k = max(1, int(top_k if top_k is not None else settings.supermemory_top_k))
        self.threshold = float(
            threshold if threshold is not None else settings.supermemory_threshold
        )
        self.timeout_seconds = max(
            1,
            int(timeout_seconds if timeout_seconds is not None else settings.supermemory_timeout_seconds),
        )
        self.transport = transport

    async def retrieve_context_lines(
        self,
        *,
        query: str,
        container_tag: str,
        user_id: str | None = None,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[str]:
        if not self.api_key:
            logger.warning("supermemory.adapter.missing_api_key")
            return []

        limit = max(1, int(top_k if top_k is not None else self.top_k))
        score_threshold = float(threshold if threshold is not None else self.threshold)
        request_payload: dict[str, object] = {
            "query": query,
            "q": query,
            "containerTag": container_tag,
            "mode": "hybrid",
            "strategy": "hybrid",
            "threshold": score_threshold,
            "limit": limit,
        }
        if user_id:
            request_payload["userId"] = user_id

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                transport=self.transport,
            ) as client:
                response = await client.post("/v4/search", json=request_payload)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            logger.warning(
                "supermemory.adapter.lookup_failed error=%s container_tag=%s",
                str(exc),
                container_tag,
            )
            return []

        if not isinstance(payload, dict):
            return []
        deduped: list[str] = []
        seen: set[str] = set()
        for line in _extract_text_candidates(payload):
            if line in seen:
                continue
            seen.add(line)
            deduped.append(line[:240])
            if len(deduped) >= limit:
                break
        return deduped


async def retrieve_arena_context_lines(
    *,
    query: str,
    container_scope: str,
    user_id: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Convenience wrapper used by task-mode execution for arena context lookup."""
    adapter = SupermemoryAdapter()
    container_tag = build_container_tag(
        prefix=settings.supermemory_container_tag_prefix,
        scope=container_scope,
    )
    return await adapter.retrieve_context_lines(
        query=query,
        container_tag=container_tag,
        user_id=user_id,
        top_k=limit,
    )
