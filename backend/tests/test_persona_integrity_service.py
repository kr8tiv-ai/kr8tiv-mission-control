from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.agent_persona_integrity import AgentPersonaIntegrity
from app.models.agents import Agent
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.services.openclaw.persona_integrity_service import PersonaIntegrityService


def _persona_files(*, soul: str, user: str, identity: str, agents: str) -> dict[str, str]:
    return {
        "SOUL.md": soul,
        "USER.md": user,
        "IDENTITY.md": identity,
        "AGENTS.md": agents,
    }


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


async def _seed_agent(session: AsyncSession) -> Agent:
    org = Organization(id=uuid4(), name="KR8TIV")
    gateway = Gateway(
        id=uuid4(),
        organization_id=org.id,
        name="prod-gateway",
        url="ws://gateway.example/ws",
        workspace_root="/tmp/openclaw",
    )
    agent = Agent(
        id=uuid4(),
        gateway_id=gateway.id,
        board_id=None,
        name="Friday",
    )
    session.add(org)
    session.add(gateway)
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


@pytest.mark.asyncio
async def test_persona_integrity_service_creates_baseline_when_missing() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            agent = await _seed_agent(session)
            service = PersonaIntegrityService(session)
            files = _persona_files(
                soul="core voice",
                user="owner profile",
                identity="identity contract",
                agents="runtime contract",
            )

            result = await service.verify_persona_integrity(
                agent_id=agent.id,
                file_contents=files,
            )

            assert result.baseline_created is True
            assert result.drift_detected is False
            assert result.drift_fields == []
            assert result.drift_count == 0
            rows = await AgentPersonaIntegrity.objects.filter_by(agent_id=agent.id).all(session)
            assert len(rows) == 1
            assert rows[0].drift_count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_persona_integrity_service_detects_drift() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            agent = await _seed_agent(session)
            service = PersonaIntegrityService(session)
            baseline_files = _persona_files(
                soul="core voice",
                user="owner profile",
                identity="identity contract",
                agents="runtime contract",
            )
            await service.verify_persona_integrity(
                agent_id=agent.id,
                file_contents=baseline_files,
            )

            drift_result = await service.verify_persona_integrity(
                agent_id=agent.id,
                file_contents=_persona_files(
                    soul="core voice changed",
                    user="owner profile",
                    identity="identity contract",
                    agents="runtime contract",
                ),
            )

            assert drift_result.baseline_created is False
            assert drift_result.drift_detected is True
            assert drift_result.drift_fields == ["SOUL.md"]
            assert drift_result.drift_count == 1
            rows = await AgentPersonaIntegrity.objects.filter_by(agent_id=agent.id).all(session)
            assert len(rows) == 1
            assert rows[0].drift_count == 1
            assert rows[0].last_drift_fields == ["SOUL.md"]
            assert rows[0].last_drift_at is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_persona_integrity_service_reset_baseline_clears_drift() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            agent = await _seed_agent(session)
            service = PersonaIntegrityService(session)
            baseline_files = _persona_files(
                soul="v1 soul",
                user="v1 user",
                identity="v1 identity",
                agents="v1 agents",
            )
            await service.verify_persona_integrity(
                agent_id=agent.id,
                file_contents=baseline_files,
            )
            changed_files = _persona_files(
                soul="v2 soul",
                user="v2 user",
                identity="v2 identity",
                agents="v2 agents",
            )
            drift_result = await service.verify_persona_integrity(
                agent_id=agent.id,
                file_contents=changed_files,
            )
            assert drift_result.drift_detected is True

            await service.reset_baseline(
                agent_id=agent.id,
                file_contents=changed_files,
            )
            verify_after_reset = await service.verify_persona_integrity(
                agent_id=agent.id,
                file_contents=changed_files,
            )

            assert verify_after_reset.drift_detected is False
            rows = await AgentPersonaIntegrity.objects.filter_by(agent_id=agent.id).all(session)
            assert len(rows) == 1
            assert rows[0].last_drift_fields == []
            assert rows[0].last_drift_at is None
    finally:
        await engine.dispose()
