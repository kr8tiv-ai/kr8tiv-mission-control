# ruff: noqa: S101
from __future__ import annotations

import httpx
import pytest

from app.services.supermemory_adapter import SupermemoryAdapter, build_container_tag


@pytest.mark.asyncio
async def test_retrieve_context_lines_uses_hybrid_search_and_dedupes() -> None:
    requests: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/v4/search"
        payload = request.read().decode("utf-8")
        assert '"mode":"hybrid"' in payload
        return httpx.Response(
            200,
            json={
                "results": [
                    {"content": "alpha"},
                    {"text": "beta"},
                    {"snippet": "alpha"},
                    {"content": "gamma"},
                ]
            },
        )

    adapter = SupermemoryAdapter(
        base_url="https://api.supermemory.ai",
        api_key="test-key",
        top_k=2,
        threshold=0.45,
        transport=httpx.MockTransport(_handler),
    )

    lines = await adapter.retrieve_context_lines(
        query="test query",
        container_tag="tenant:abc",
        user_id="user-1",
    )

    assert lines == ["alpha", "beta"]
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_retrieve_context_lines_degrades_gracefully_on_error() -> None:
    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    adapter = SupermemoryAdapter(
        base_url="https://api.supermemory.ai",
        api_key="test-key",
        transport=httpx.MockTransport(_handler),
    )

    lines = await adapter.retrieve_context_lines(
        query="test query",
        container_tag="tenant:abc",
    )

    assert lines == []


@pytest.mark.asyncio
async def test_retrieve_context_lines_returns_empty_without_api_key() -> None:
    called = False

    def _handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"results": [{"content": "x"}]})

    adapter = SupermemoryAdapter(
        base_url="https://api.supermemory.ai",
        api_key="",
        transport=httpx.MockTransport(_handler),
    )

    lines = await adapter.retrieve_context_lines(
        query="test query",
        container_tag="tenant:abc",
    )

    assert lines == []
    assert called is False


def test_build_container_tag_uses_prefix_and_board_scope() -> None:
    tag = build_container_tag(prefix="tenant", scope="board-123")
    assert tag == "tenant:board-123"
