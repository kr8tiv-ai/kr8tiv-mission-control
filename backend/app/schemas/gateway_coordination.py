from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlmodel import Field, SQLModel

from app.schemas.common import NonEmptyStr


class GatewayLeadMessageRequest(SQLModel):
    kind: Literal["question", "handoff"] = "question"
    correlation_id: str | None = None
    content: NonEmptyStr

    # How the lead should reply (defaults are interpreted by templates).
    reply_tags: list[str] = Field(default_factory=lambda: ["gateway_main", "lead_reply"])
    reply_source: str | None = "lead_to_gateway_main"


class GatewayLeadMessageResponse(SQLModel):
    ok: bool = True
    board_id: UUID
    lead_agent_id: UUID | None = None
    lead_agent_name: str | None = None
    lead_created: bool = False


class GatewayLeadBroadcastRequest(SQLModel):
    kind: Literal["question", "handoff"] = "question"
    correlation_id: str | None = None
    content: NonEmptyStr
    board_ids: list[UUID] | None = None
    reply_tags: list[str] = Field(default_factory=lambda: ["gateway_main", "lead_reply"])
    reply_source: str | None = "lead_to_gateway_main"


class GatewayLeadBroadcastBoardResult(SQLModel):
    board_id: UUID
    lead_agent_id: UUID | None = None
    lead_agent_name: str | None = None
    ok: bool = False
    error: str | None = None


class GatewayLeadBroadcastResponse(SQLModel):
    ok: bool = True
    sent: int = 0
    failed: int = 0
    results: list[GatewayLeadBroadcastBoardResult] = Field(default_factory=list)


class GatewayMainAskUserRequest(SQLModel):
    correlation_id: str | None = None
    content: NonEmptyStr
    preferred_channel: str | None = None

    # How the main agent should reply back into Mission Control (defaults interpreted by templates).
    reply_tags: list[str] = Field(default_factory=lambda: ["gateway_main", "user_reply"])
    reply_source: str | None = "user_via_gateway_main"


class GatewayMainAskUserResponse(SQLModel):
    ok: bool = True
    board_id: UUID
    main_agent_id: UUID | None = None
    main_agent_name: str | None = None
