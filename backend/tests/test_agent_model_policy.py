# ruff: noqa: S101
"""Tests for Mission Control agent model-policy locking."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.models.agents import Agent
from app.services.openclaw.model_policy import (
    enforce_agent_model_policy,
    locked_model_policy_for_name,
    model_id_for_policy,
    normalize_model_policy,
)
from app.services.openclaw.provisioning_db import AgentLifecycleService


@dataclass
class _FakeSession:
    def add(self, _value: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def refresh(self, _value: object) -> None:
        return None


def test_locked_model_policy_lookup_for_named_agents() -> None:
    friday = locked_model_policy_for_name("Friday")
    arsenal = locked_model_policy_for_name("arsenal")
    edith = locked_model_policy_for_name("EDITH")
    jocasta = locked_model_policy_for_name("jocasta")

    assert friday is not None
    assert arsenal is not None
    assert edith is not None
    assert jocasta is not None
    assert friday["model"] == "openai-codex/gpt-5.3-codex"
    assert arsenal["transport"] == "cli"
    assert edith["provider"] == "google-gemini-cli"
    assert edith["model"] == "google-gemini-cli/gemini-3-pro-preview"
    assert jocasta["model"] == "nvidia/moonshotai/kimi-k2.5"


def test_normalize_model_policy_maps_legacy_aliases() -> None:
    normalized = normalize_model_policy(
        {
            "provider": "google-gemini-cli",
            "model": "google-gemini-cli/gemini-3.1",
            "transport": "cli",
            "locked": True,
        },
    )

    assert normalized is not None
    assert normalized["model"] == "google-gemini-cli/gemini-3-pro-preview"
    assert (
        model_id_for_policy(
            {
                "provider": "google-gemini-cli",
                "model": "google-gemini-cli/gemini-3.1",
                "transport": "cli",
            },
        )
        == "google-gemini-cli/gemini-3-pro-preview"
    )


def test_enforce_agent_model_policy_rewrites_legacy_locked_model() -> None:
    agent = Agent(
        id=uuid4(),
        name="EDITH",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        model_policy={
            "provider": "google-gemini-cli",
            "model": "google-gemini-cli/gemini-3.1",
            "transport": "cli",
            "locked": True,
            "allow_self_change": False,
        },
    )

    changed = enforce_agent_model_policy(agent)

    assert changed is True
    normalized = normalize_model_policy(agent.model_policy)
    assert normalized is not None
    assert normalized["model"] == "google-gemini-cli/gemini-3-pro-preview"


@pytest.mark.asyncio
async def test_persist_new_agent_applies_locked_policy_over_requested_policy() -> None:
    service = AgentLifecycleService(_FakeSession())  # type: ignore[arg-type]

    agent, _raw_token = await service.persist_new_agent(
        data={
            "name": "Friday",
            "board_id": uuid4(),
            "gateway_id": uuid4(),
            "heartbeat_config": {"every": "10m"},
            "model_policy": {
                "provider": "openai-codex",
                "model": "openai-codex/gpt-4.1",
                "transport": "api",
                "locked": False,
            },
        },
    )

    normalized = normalize_model_policy(agent.model_policy)
    assert normalized is not None
    assert normalized["model"] == "openai-codex/gpt-5.3-codex"
    assert normalized["transport"] == "cli"
    assert normalized["locked"] is True


@pytest.mark.asyncio
async def test_apply_agent_update_mutations_rejects_locked_policy_changes() -> None:
    service = AgentLifecycleService(_FakeSession())  # type: ignore[arg-type]
    locked_policy = locked_model_policy_for_name("Arsenal")
    assert locked_policy is not None
    agent = Agent(
        id=uuid4(),
        name="Arsenal",
        board_id=uuid4(),
        gateway_id=uuid4(),
        status="online",
        model_policy=locked_policy,
        heartbeat_config={"every": "10m"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.apply_agent_update_mutations(
            agent=agent,
            updates={
                "model_policy": {
                    "provider": "openai-codex",
                    "model": "openai-codex/gpt-4.1",
                    "transport": "api",
                    "locked": False,
                },
            },
            make_main=None,
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "model_policy is locked" in str(exc_info.value.detail)
