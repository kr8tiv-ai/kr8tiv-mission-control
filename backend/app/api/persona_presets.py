"""Persona preset APIs for org-scoped reusable agent personalities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select

from app.api.deps import require_org_admin
from app.core.time import utcnow
from app.db.session import get_session
from app.models.agents import Agent
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

router = APIRouter(prefix="/persona-presets", tags=["agents"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


@router.post(
    "",
    response_model=PersonaPresetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_persona_preset(
    payload: PersonaPresetCreate,
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> PersonaPreset:
    preset = PersonaPreset(
        organization_id=org_ctx.organization.id,
        name=payload.name,
        description=payload.description,
        preset_mode=payload.preset_mode,
        identity_profile=payload.identity_profile,
        identity_template=payload.identity_template,
        soul_template=payload.soul_template,
    )
    session.add(preset)
    await session.commit()
    await session.refresh(preset)
    return preset


@router.get(
    "",
    response_model=list[PersonaPresetRead],
)
async def list_persona_presets(
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> list[PersonaPreset]:
    return (
        await session.exec(
            select(PersonaPreset)
            .where(col(PersonaPreset.organization_id) == org_ctx.organization.id)
            .order_by(PersonaPreset.name),
        )
    ).all()


@router.post(
    "/agents/{agent_id}/apply",
    response_model=PersonaPresetApplyResponse,
)
async def apply_persona_preset(
    agent_id: UUID,
    payload: PersonaPresetApplyRequest,
    org_ctx: OrganizationContext = ORG_ADMIN_DEP,
    session: AsyncSession = SESSION_DEP,
) -> PersonaPresetApplyResponse:
    preset = (
        await session.exec(
            select(PersonaPreset).where(
                col(PersonaPreset.id) == payload.preset_id,
                col(PersonaPreset.organization_id) == org_ctx.organization.id,
            ),
        )
    ).first()
    if preset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona preset not found",
        )

    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    gateway = await session.get(Gateway, agent.gateway_id)
    if gateway is None or gateway.organization_id != org_ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if preset.identity_profile is not None:
        agent.identity_profile = preset.identity_profile
    if preset.identity_template is not None:
        agent.identity_template = preset.identity_template
    if preset.soul_template is not None:
        agent.soul_template = preset.soul_template
    agent.updated_at = utcnow()

    session.add(agent)
    await session.commit()

    return PersonaPresetApplyResponse(
        applied=True,
        agent_id=agent.id,
        preset_id=preset.id,
    )
