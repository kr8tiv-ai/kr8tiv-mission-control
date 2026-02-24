# ruff: noqa: INP001

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import board_onboarding
from app.models.board_onboarding import BoardOnboardingSession
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.onboarding_recommendations import OnboardingRecommendation
from app.models.organizations import Organization


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def test_onboarding_qa_generates_persona_and_ability_recommendation() -> None:
    recommendation = board_onboarding._build_onboarding_recommendation(
        {
            "lead_agent": {
                "identity_profile": {
                    "role": "Board Lead",
                },
            },
        },
    )

    assert recommendation["recommended_preset"] == "team_orchestrated_default"
    assert recommendation["deployment_mode"] == "team"
    supermemory_capability = next(
        cap for cap in recommendation["capabilities"] if cap["key"] == "supermemory_plugin"
    )
    assert supermemory_capability["required"] is True
    assert (
        supermemory_capability["install_command"]
        == "openclaw plugins install @supermemory/openclaw-supermemory"
    )


def test_personalized_flow_defaults_voice_and_uplay_chromium_capability() -> None:
    recommendation = board_onboarding._build_onboarding_recommendation(
        {
            "deployment_mode": "individual",
        },
    )

    assert recommendation["deployment_mode"] == "individual"
    assert recommendation["voice_enabled"] is True
    assert recommendation["computer_automation_profile"] == "uplay_chromium"
    capability_keys = {cap["key"] for cap in recommendation["capabilities"]}
    assert "voice_model" in capability_keys
    assert "uplay_chromium_automation" in capability_keys
    assert "supermemory_plugin" in capability_keys


@pytest.mark.asyncio
async def test_recommendation_upsert_persists_for_board() -> None:
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            org_id = uuid4()
            gateway_id = uuid4()
            board_id = uuid4()
            onboarding_id = uuid4()
            session.add(Organization(id=org_id, name="Org One"))
            session.add(
                Gateway(
                    id=gateway_id,
                    organization_id=org_id,
                    name="Gateway One",
                    url="https://gateway.example.local",
                    workspace_root="/workspace/openclaw",
                ),
            )
            session.add(
                Board(
                    id=board_id,
                    organization_id=org_id,
                    gateway_id=gateway_id,
                    name="Board One",
                    slug="board-one",
                    description="Board",
                    board_type="goal",
                ),
            )
            session.add(
                BoardOnboardingSession(
                    id=onboarding_id,
                    board_id=board_id,
                    session_key="onboarding:key",
                    status="completed",
                ),
            )
            await session.commit()

            recommendation = board_onboarding._build_onboarding_recommendation(
                {"deployment_mode": "individual"},
            )
            await board_onboarding._upsert_onboarding_recommendation(
                session=session,
                board_id=board_id,
                onboarding_session_id=onboarding_id,
                recommendation=recommendation,
            )
            await session.commit()

            stored = (
                await session.exec(
                    select(OnboardingRecommendation).where(
                        OnboardingRecommendation.board_id == board_id,
                    ),
                )
            ).first()

            assert stored is not None
            assert stored.deployment_mode == "individual"
            assert stored.voice_enabled is True
            assert stored.computer_automation_profile == "uplay_chromium"
    finally:
        await engine.dispose()
