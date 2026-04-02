from __future__ import annotations

from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, get_auth_context
from app.core.config import settings

router = APIRouter(prefix="/friday", tags=["friday"])
AUTH_CONTEXT_DEP = Depends(get_auth_context)
LIMIT_QUERY = Query(default=8, ge=1, le=50)


class FridayChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(default=None, max_length=255)


class FridayChatResponse(BaseModel):
    response: str
    provider: str = "zhipuai"
    model: str = "glm-5"
    memory_ids: list[str] = Field(default_factory=list)


class FridayAgentStatus(BaseModel):
    id: str
    label: str
    status: Literal["online", "offline", "degraded", "unknown"]
    model: str | None = None
    interface: str | None = None
    detail: str | None = None


class FridayStatusResponse(BaseModel):
    provider: str = "zhipuai"
    model: str = "glm-5"
    service_url: str
    reachable: bool
    detail: str | None = None
    agents: list[FridayAgentStatus]


class FridayMemoryItem(BaseModel):
    id: str | None = None
    content: str
    created_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class FridayMemoryResponse(BaseModel):
    reachable: bool
    items: list[FridayMemoryItem]


class FridayTelegramLogItem(BaseModel):
    id: str | None = None
    direction: Literal["incoming", "outgoing", "system"] = "system"
    chat_id: str | None = None
    text: str
    timestamp: str | None = None


class FridayTelegramLogsResponse(BaseModel):
    reachable: bool
    items: list[FridayTelegramLogItem]


def _require_user(auth: AuthContext) -> None:
    if auth.actor_type != "user" or auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def _fallback_agents() -> list[FridayAgentStatus]:
    return [
        FridayAgentStatus(
            id="friday",
            label="Friday",
            status="online",
            model="glm-5",
            interface="telegram + mission-control",
            detail="Primary KR8TIV operator",
        ),
        FridayAgentStatus(
            id="arsenal",
            label="Arsenal",
            status="offline",
            detail="Offline by policy",
        ),
        FridayAgentStatus(
            id="edith",
            label="Edith",
            status="offline",
            detail="Offline by policy",
        ),
        FridayAgentStatus(
            id="jocasta",
            label="Jocasta",
            status="offline",
            detail="Offline by policy",
        ),
    ]


async def _friday_request(
    *,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_url = settings.friday_api_url.rstrip("/")
    timeout = settings.friday_api_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method=method,
            url=f"{base_url}{path}",
            json=json_body,
            params=params,
        )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Friday service returned an invalid response.",
        )
    return payload


@router.get("/status", response_model=FridayStatusResponse)
async def get_friday_status(auth: AuthContext = AUTH_CONTEXT_DEP) -> FridayStatusResponse:
    _require_user(auth)
    try:
        payload = await _friday_request(method="GET", path="/status")
    except httpx.HTTPError as exc:
        return FridayStatusResponse(
            service_url=settings.friday_api_url,
            reachable=False,
            detail=str(exc),
            agents=_fallback_agents(),
        )

    raw_agents = payload.get("agents")
    agents: list[FridayAgentStatus] = []
    if isinstance(raw_agents, list):
        for index, item in enumerate(raw_agents):
            if not isinstance(item, dict):
                continue
            agent_id = str(item.get("id") or f"agent-{index}")
            label = str(item.get("label") or agent_id.title())
            raw_status = str(item.get("status") or "unknown").lower()
            status_value: Literal["online", "offline", "degraded", "unknown"]
            if raw_status in {"online", "offline", "degraded", "unknown"}:
                status_value = raw_status  # type: ignore[assignment]
            else:
                status_value = "unknown"
            agents.append(
                FridayAgentStatus(
                    id=agent_id,
                    label=label,
                    status=status_value,
                    model=(str(item.get("model")) if item.get("model") else None),
                    interface=(str(item.get("interface")) if item.get("interface") else None),
                    detail=(str(item.get("detail")) if item.get("detail") else None),
                )
            )

    return FridayStatusResponse(
        provider=str(payload.get("provider") or "zhipuai"),
        model=str(payload.get("model") or "glm-5"),
        service_url=settings.friday_api_url,
        reachable=bool(payload.get("reachable", True)),
        detail=(str(payload.get("detail")) if payload.get("detail") else None),
        agents=agents or _fallback_agents(),
    )


@router.post("/chat", response_model=FridayChatResponse)
async def chat_with_friday(
    payload: FridayChatRequest,
    auth: AuthContext = AUTH_CONTEXT_DEP,
) -> FridayChatResponse:
    _require_user(auth)
    try:
        response_payload = await _friday_request(
            method="POST",
            path="/chat",
            json_body=payload.model_dump(exclude_none=True),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Friday service is unavailable: {exc}",
        ) from exc

    response_text = response_payload.get("response")
    if not isinstance(response_text, str) or not response_text.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Friday service returned an empty response.",
        )

    raw_memory_ids = response_payload.get("memory_ids")
    memory_ids = [str(item) for item in raw_memory_ids] if isinstance(raw_memory_ids, list) else []
    return FridayChatResponse(
        response=response_text,
        provider=str(response_payload.get("provider") or "zhipuai"),
        model=str(response_payload.get("model") or "glm-5"),
        memory_ids=memory_ids,
    )


@router.get("/memory/recent", response_model=FridayMemoryResponse)
async def get_friday_memory_recent(
    limit: int = LIMIT_QUERY,
    auth: AuthContext = AUTH_CONTEXT_DEP,
) -> FridayMemoryResponse:
    _require_user(auth)
    try:
        payload = await _friday_request(
            method="GET",
            path="/memory/recent",
            params={"limit": limit},
        )
    except httpx.HTTPError:
        return FridayMemoryResponse(reachable=False, items=[])

    raw_items = payload.get("items")
    items: list[FridayMemoryItem] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            raw_tags = item.get("tags")
            tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
            items.append(
                FridayMemoryItem(
                    id=(str(item.get("id")) if item.get("id") else None),
                    content=content,
                    created_at=(str(item.get("created_at")) if item.get("created_at") else None),
                    tags=tags,
                )
            )
    return FridayMemoryResponse(reachable=bool(payload.get("reachable", True)), items=items)


@router.get("/telegram/logs", response_model=FridayTelegramLogsResponse)
async def get_friday_telegram_logs(
    limit: int = LIMIT_QUERY,
    auth: AuthContext = AUTH_CONTEXT_DEP,
) -> FridayTelegramLogsResponse:
    _require_user(auth)
    try:
        payload = await _friday_request(
            method="GET",
            path="/telegram/logs",
            params={"limit": limit},
        )
    except httpx.HTTPError:
        return FridayTelegramLogsResponse(reachable=False, items=[])

    raw_items = payload.get("items")
    items: list[FridayTelegramLogItem] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            raw_direction = str(item.get("direction") or "system").lower()
            direction: Literal["incoming", "outgoing", "system"]
            if raw_direction in {"incoming", "outgoing", "system"}:
                direction = raw_direction  # type: ignore[assignment]
            else:
                direction = "system"
            items.append(
                FridayTelegramLogItem(
                    id=(str(item.get("id")) if item.get("id") else None),
                    direction=direction,
                    chat_id=(str(item.get("chat_id")) if item.get("chat_id") else None),
                    text=text,
                    timestamp=(str(item.get("timestamp")) if item.get("timestamp") else None),
                )
            )
    return FridayTelegramLogsResponse(reachable=bool(payload.get("reachable", True)), items=items)
