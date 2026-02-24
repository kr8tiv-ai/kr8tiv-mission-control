from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import runtime as runtime_api
from app.api.deps import ActorContext
from app.models.boards import Board
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.pack_bindings import PackBinding
from app.models.prompt_packs import PromptPack
from app.models.users import User
from app.services.control_plane import resolve_pack_binding


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_scope_resolution_precedence_user_over_org_domain_global() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org = Organization(id=uuid4(), name="org")
            user = User(id=uuid4(), clerk_user_id="clerk-user-1", email="u1@example.com")
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

            global_pack = PromptPack(
                organization_id=None,
                scope="global",
                scope_ref="",
                tier="personal",
                pack_key="engineering-delivery-pack",
                version=1,
                policy={"name": "global"},
                pack_metadata={},
            )
            domain_pack = PromptPack(
                organization_id=None,
                scope="domain",
                scope_ref="engineering",
                tier="personal",
                pack_key="engineering-delivery-pack",
                version=2,
                policy={"name": "domain"},
                pack_metadata={},
            )
            org_pack = PromptPack(
                organization_id=org.id,
                scope="organization",
                scope_ref="",
                tier="personal",
                pack_key="engineering-delivery-pack",
                version=3,
                policy={"name": "organization"},
                pack_metadata={},
            )
            user_pack = PromptPack(
                organization_id=org.id,
                scope="user",
                scope_ref=str(user.id),
                tier="personal",
                pack_key="engineering-delivery-pack",
                version=4,
                policy={"name": "user"},
                pack_metadata={},
            )
            session.add(global_pack)
            session.add(domain_pack)
            session.add(org_pack)
            session.add(user_pack)
            await session.flush()

            session.add(
                PackBinding(
                    organization_id=None,
                    scope="global",
                    scope_ref="",
                    tier="personal",
                    pack_key="engineering-delivery-pack",
                    champion_pack_id=global_pack.id,
                )
            )
            session.add(
                PackBinding(
                    organization_id=None,
                    scope="domain",
                    scope_ref="engineering",
                    tier="personal",
                    pack_key="engineering-delivery-pack",
                    champion_pack_id=domain_pack.id,
                )
            )
            session.add(
                PackBinding(
                    organization_id=org.id,
                    scope="organization",
                    scope_ref="",
                    tier="personal",
                    pack_key="engineering-delivery-pack",
                    champion_pack_id=org_pack.id,
                )
            )
            session.add(
                PackBinding(
                    organization_id=org.id,
                    scope="user",
                    scope_ref=str(user.id),
                    tier="personal",
                    pack_key="engineering-delivery-pack",
                    champion_pack_id=user_pack.id,
                )
            )
            await session.commit()

            resolved = await resolve_pack_binding(
                session,
                organization_id=org.id,
                user_id=user.id,
                domain="engineering",
                tier="personal",
                pack_key="engineering-delivery-pack",
            )
            assert resolved is not None
            assert resolved.pack.id == user_pack.id
            assert any(entry.startswith("global:") for entry in resolved.resolved_chain)
            assert any(entry.startswith("domain:") for entry in resolved.resolved_chain)
            assert any(entry.startswith("organization:") for entry in resolved.resolved_chain)
            assert any(entry.startswith("user:") for entry in resolved.resolved_chain)

            resolved_without_user = await resolve_pack_binding(
                session,
                organization_id=org.id,
                user_id=None,
                domain="engineering",
                tier="personal",
                pack_key="engineering-delivery-pack",
            )
            assert resolved_without_user is not None
            assert resolved_without_user.pack.id == org_pack.id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_pack_resolve_blocks_cross_org_board_access() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org_a = Organization(id=uuid4(), name="org-a")
            org_b = Organization(id=uuid4(), name="org-b")
            user_b = User(id=uuid4(), clerk_user_id="clerk-user-2", email="u2@example.com")
            board_a = Board(
                id=uuid4(),
                organization_id=org_a.id,
                name="board-a",
                slug="board-a",
            )
            session.add(org_a)
            session.add(org_b)
            session.add(user_b)
            session.add(board_a)
            session.add(
                OrganizationMember(
                    organization_id=org_b.id,
                    user_id=user_b.id,
                    role="owner",
                    all_boards_read=True,
                    all_boards_write=True,
                )
            )
            await session.commit()

            actor = ActorContext(actor_type="user", user=user_b)
            with pytest.raises(HTTPException) as exc:
                await runtime_api.resolve_runtime_pack(
                    board_id=board_a.id,
                    tier="personal",
                    pack_key="engineering-delivery-pack",
                    domain="",
                    session=session,
                    actor=actor,
                )
            assert exc.value.status_code == 403
    finally:
        await engine.dispose()
