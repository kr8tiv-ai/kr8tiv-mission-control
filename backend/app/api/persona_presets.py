"""Persona preset catalog and apply endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.persona_presets import PersonaPreset
from app.schemas.persona_presets import (
    PersonaPresetApplyRequest,
    PersonaPresetApplyResponse,
    PersonaPresetCreate,
    PersonaPresetRead,
)
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/persona-presets", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


def _as_read(preset: PersonaPreset) -> PersonaPresetRead:
    return PersonaPresetRead(
        id=preset.id,
        organization_id=preset.organization_id,
        key=preset.key,
        name=preset.name,
        description=preset.description,
        deployment_mode=preset.deployment_mode,
        identity_profile=preset.identity_profile,
        identity_template=preset.identity_template,
        soul_template=preset.soul_template,
        metadata_=preset.metadata_ or {},
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


async def _require_preset(
    *,
    session: AsyncSession,
    preset_id: UUID,
    organization_id: UUID,
) -> PersonaPreset:
    preset = await PersonaPreset.objects.by_id(preset_id).first(session)
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if preset.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return preset


async def _require_agent_for_org(
    *,
    session: AsyncSession,
    agent_id: UUID,
    organization_id: UUID,
) -> Agent:
    agent = await Agent.objects.by_id(agent_id).first(session)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if agent.board_id is not None:
        board = await Board.objects.by_id(agent.board_id).first(session)
        if board is None or board.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return agent

    gateway = await Gateway.objects.by_id(agent.gateway_id).first(session)
    if gateway is None or gateway.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return agent


@router.get("", response_model=list[PersonaPresetRead])
async def list_persona_presets(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> list[PersonaPresetRead]:
    """List persona presets in the active organization."""
    statement = (
        select(PersonaPreset)
        .where(col(PersonaPreset.organization_id) == ctx.organization.id)
        .order_by(col(PersonaPreset.created_at).asc())
    )
    presets = (await session.exec(statement)).all()
    return [_as_read(preset) for preset in presets]


@router.post("", response_model=PersonaPresetRead)
async def create_persona_preset(
    payload: PersonaPresetCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> PersonaPresetRead:
    """Create a persona preset in the active organization."""
    existing = await PersonaPreset.objects.filter_by(
        organization_id=ctx.organization.id,
        key=payload.key,
    ).first(session)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preset key already exists in this organization.",
        )

    preset = PersonaPreset(
        organization_id=ctx.organization.id,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        deployment_mode=payload.deployment_mode,
        identity_profile=payload.identity_profile,
        identity_template=payload.identity_template,
        soul_template=payload.soul_template,
        metadata_=dict(payload.metadata_),
    )
    session.add(preset)
    await session.commit()
    await session.refresh(preset)
    return _as_read(preset)


@router.post("/agents/{agent_id}/apply", response_model=PersonaPresetApplyResponse)
async def apply_persona_preset(
    agent_id: UUID,
    payload: PersonaPresetApplyRequest,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> PersonaPresetApplyResponse:
    """Apply a persona preset to an existing agent."""
    preset = await _require_preset(
        session=session,
        preset_id=payload.preset_id,
        organization_id=ctx.organization.id,
    )
    agent = await _require_agent_for_org(
        session=session,
        agent_id=agent_id,
        organization_id=ctx.organization.id,
    )

    if preset.identity_profile is not None:
        agent.identity_profile = dict(preset.identity_profile)
    agent.identity_template = preset.identity_template
    agent.soul_template = preset.soul_template
    agent.updated_at = utcnow()
    session.add(agent)
    await session.commit()

    return PersonaPresetApplyResponse(
        agent_id=agent.id,
        preset_id=preset.id,
    )
