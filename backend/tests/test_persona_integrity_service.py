from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.agents import Agent
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.services.openclaw.persona_integrity_service import PersonaIntegrityService


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _seed_agent(session: AsyncSession) -> UUID:
    org_id = uuid4()
    gateway_id = uuid4()
    agent_id = uuid4()
    session.add(Organization(id=org_id, name=f"org-{org_id}"))
    session.add(
        Gateway(
            id=gateway_id,
            organization_id=org_id,
            name="gateway",
            url="ws://gateway.example/ws",
            workspace_root="/tmp/openclaw",
        ),
    )
    session.add(Agent(id=agent_id, gateway_id=gateway_id, name="Friday", status="online"))
    await session.commit()
    return agent_id


@pytest.mark.asyncio
async def test_persona_integrity_service_detects_drift() -> None:
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            agent_id = await _seed_agent(session)
            service = PersonaIntegrityService(session)
            baseline_files = {
                "SOUL.md": "core identity",
                "USER.md": "owner preferences",
                "IDENTITY.md": "role: cmo",
                "AGENTS.md": "task rules",
            }

            baseline = await service.create_or_update_baseline(
                agent_id=agent_id,
                file_contents=baseline_files,
            )
            assert baseline.drift_count == 0

            drift = await service.detect_drift(
                agent_id=agent_id,
                file_contents={
                    **baseline_files,
                    "USER.md": "owner preferences changed",
                },
            )

            assert drift.has_drift is True
            assert drift.drifted_files == ["USER.md"]

            stored = await service.get_baseline(agent_id)
            assert stored is not None
            assert stored.drift_count == 1
            assert stored.last_drift_at is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_persona_integrity_service_returns_clean_when_no_drift() -> None:
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            agent_id = await _seed_agent(session)
            service = PersonaIntegrityService(session)
            file_contents = {
                "SOUL.md": "core identity",
                "USER.md": "owner preferences",
                "IDENTITY.md": "role: cmo",
                "AGENTS.md": "task rules",
            }

            await service.create_or_update_baseline(
                agent_id=agent_id,
                file_contents=file_contents,
            )
            drift = await service.detect_drift(agent_id=agent_id, file_contents=file_contents)

            assert drift.has_drift is False
            assert drift.drifted_files == []

            stored = await service.get_baseline(agent_id)
            assert stored is not None
            assert stored.drift_count == 0
            assert stored.last_drift_at is None
    finally:
        await engine.dispose()
