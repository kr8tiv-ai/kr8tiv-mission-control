from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import packs as packs_api
from app.core.auth import AuthContext
from app.models.deterministic_evals import DeterministicEval
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.pack_bindings import PackBinding
from app.models.prompt_packs import PromptPack
from app.models.promotion_events import PromotionEvent
from app.models.run_telemetry import RunTelemetry
from app.models.users import User
from app.schemas.control_plane import (
    PackPromotionRequest,
    PackRollbackRequest,
    PromptPackCreateRequest,
)
from app.services.organizations import OrganizationContext


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


async def _seed_org_user(session: AsyncSession) -> tuple[Organization, User, OrganizationMember]:
    org = Organization(id=uuid4(), name="org")
    user = User(id=uuid4(), clerk_user_id="clerk-user", email="owner@example.com")
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="owner",
        all_boards_read=True,
        all_boards_write=True,
    )
    session.add(org)
    session.add(user)
    session.add(member)
    await session.flush()
    return org, user, member


async def _add_eval(
    session: AsyncSession,
    *,
    organization_id,
    pack_id,
    pack_key: str,
    score: float,
    hard_regression: bool,
) -> None:
    run = RunTelemetry(
        organization_id=organization_id,
        pack_id=pack_id,
        pack_key=pack_key,
        tier="personal",
        success_bool=True,
        retries=0,
        latency_ms=100,
        format_contract_passed=True,
        approval_gate_passed=True,
        checks={
            "pr_created": True,
            "ci_passed": True,
            "human_reviewed": True,
        },
        run_metadata={"lane": "engineering_swarm"},
    )
    session.add(run)
    await session.flush()
    session.add(
        DeterministicEval(
            run_telemetry_id=run.id,
            organization_id=organization_id,
            pack_id=pack_id,
            pack_key=pack_key,
            tier="personal",
            success_bool=True,
            retries=0,
            latency_regression_pct=0.0,
            format_contract_compliance=True,
            approval_gate_compliance=True,
            score=score,
            hard_regression=hard_regression,
            details={},
        )
    )


@pytest.mark.asyncio
async def test_promote_pack_blocks_on_regression() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member = await _seed_org_user(session)
            champion = PromptPack(
                organization_id=org.id,
                scope="organization",
                scope_ref="",
                tier="personal",
                pack_key="engineering-delivery-pack",
                version=1,
                policy={"name": "champion"},
                pack_metadata={},
            )
            challenger = PromptPack(
                organization_id=org.id,
                scope="organization",
                scope_ref="",
                tier="personal",
                pack_key="engineering-delivery-pack",
                version=2,
                policy={"name": "challenger"},
                pack_metadata={},
            )
            session.add(champion)
            session.add(challenger)
            await session.flush()

            session.add(
                PackBinding(
                    organization_id=org.id,
                    scope="organization",
                    scope_ref="",
                    tier="personal",
                    pack_key="engineering-delivery-pack",
                    champion_pack_id=champion.id,
                )
            )

            await _add_eval(
                session,
                organization_id=org.id,
                pack_id=champion.id,
                pack_key="engineering-delivery-pack",
                score=88.0,
                hard_regression=False,
            )
            await _add_eval(
                session,
                organization_id=org.id,
                pack_id=challenger.id,
                pack_key="engineering-delivery-pack",
                score=70.0,
                hard_regression=False,
            )
            await session.commit()

            auth = AuthContext(actor_type="user", user=user)
            ctx = OrganizationContext(organization=org, member=member)

            with pytest.raises(HTTPException) as exc:
                await packs_api.promote_pack(
                    pack_id=challenger.id,
                    payload=PackPromotionRequest(
                        pack_key="engineering-delivery-pack",
                        scope="organization",
                        tier="personal",
                        min_improvement_pct=5,
                    ),
                    session=session,
                    auth=auth,
                    ctx=ctx,
                )
            assert exc.value.status_code == 409
            assert "minimum improvement" in str(exc.value.detail)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_pack_applies_tier_policy_preset_when_policy_empty() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member = await _seed_org_user(session)
            auth = AuthContext(actor_type="user", user=user)
            ctx = OrganizationContext(organization=org, member=member)

            created = await packs_api.create_pack(
                payload=PromptPackCreateRequest(
                    pack_key="engineering-delivery-pack",
                    scope="organization",
                    tier="enterprise",
                    policy={},
                ),
                session=session,
                auth=auth,
                ctx=ctx,
            )
            assert created.tier == "enterprise"
            assert created.policy["autonomy_mode"] == "governed"
            assert created.policy["external_writes"] == "ask_first"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rollback_pack_reactivates_previous_champion() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member = await _seed_org_user(session)
            old_pack = PromptPack(
                organization_id=org.id,
                scope="organization",
                scope_ref="",
                tier="personal",
                pack_key="engineering-delivery-pack",
                version=1,
                policy={"name": "old"},
                pack_metadata={},
            )
            new_pack = PromptPack(
                organization_id=org.id,
                scope="organization",
                scope_ref="",
                tier="personal",
                pack_key="engineering-delivery-pack",
                version=2,
                policy={"name": "new"},
                pack_metadata={},
            )
            session.add(old_pack)
            session.add(new_pack)
            await session.flush()

            binding = PackBinding(
                organization_id=org.id,
                scope="organization",
                scope_ref="",
                tier="personal",
                pack_key="engineering-delivery-pack",
                champion_pack_id=new_pack.id,
            )
            session.add(binding)
            await session.flush()

            session.add(
                PromotionEvent(
                    organization_id=org.id,
                    binding_id=binding.id,
                    event_type="promote",
                    from_pack_id=old_pack.id,
                    to_pack_id=new_pack.id,
                    triggered_by_user_id=user.id,
                    reason="promote",
                    metrics={},
                )
            )
            await session.commit()

            auth = AuthContext(actor_type="user", user=user)
            ctx = OrganizationContext(organization=org, member=member)
            response = await packs_api.rollback_pack(
                pack_id=new_pack.id,
                payload=PackRollbackRequest(
                    pack_key="engineering-delivery-pack",
                    scope="organization",
                    tier="personal",
                ),
                session=session,
                auth=auth,
                ctx=ctx,
            )

            assert response.promoted is False
            assert response.previous_pack_id == new_pack.id
            assert response.champion_pack_id == old_pack.id
    finally:
        await engine.dispose()
