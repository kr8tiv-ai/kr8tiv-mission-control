"""Control-plane pack management routes (create/promote/rollback)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_admin_auth, require_org_admin
from app.db.session import get_session
from app.models.prompt_packs import PromptPack
from app.schemas.control_plane import (
    PackMutationResponse,
    PackPromotionRequest,
    PackRollbackRequest,
    PromptPackCreateRequest,
    PromptPackRead,
)
from app.services.control_plane import (
    eval_summary_for_pack,
    latest_non_current_pack_for_binding,
    normalize_scope_ref,
    record_promotion_event,
    select_pack_for_scope,
    upsert_pack_binding,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.core.auth import AuthContext
    from app.services.organizations import OrganizationContext

router = APIRouter(prefix="/packs", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
AUTH_DEP = Depends(require_admin_auth)
ORG_ADMIN_DEP = Depends(require_org_admin)
TIER_POLICY_PRESETS: dict[str, dict[str, object]] = {
    "personal": {
        "autonomy_mode": "balanced",
        "external_writes": "ask_first",
        "risk_default": "low",
    },
    "enterprise": {
        "autonomy_mode": "governed",
        "external_writes": "ask_first",
        "risk_default": "medium",
        "require_approval_for_medium_high_risk": True,
    },
}


def _scope_organization_id(*, scope: str, organization_id: UUID) -> UUID | None:
    if scope in {"global", "domain"}:
        return None
    return organization_id


def _assert_pack_visibility(
    *,
    pack: PromptPack,
    organization_id: UUID,
) -> None:
    if pack.organization_id is not None and pack.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def _pack_read_model(pack: PromptPack) -> PromptPackRead:
    return PromptPackRead(
        id=pack.id,
        organization_id=pack.organization_id,
        scope=pack.scope,
        scope_ref=pack.scope_ref,
        tier=pack.tier,
        pack_key=pack.pack_key,
        version=pack.version,
        description=pack.description,
        policy=pack.policy,
        metadata=pack.pack_metadata,
        created_at=pack.created_at,
        updated_at=pack.updated_at,
    )


@router.post("", response_model=PromptPackRead)
async def create_pack(
    payload: PromptPackCreateRequest,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> PromptPackRead:
    """Create a versioned prompt pack and optionally promote as champion."""
    scope_ref = normalize_scope_ref(
        payload.scope,
        payload.scope_ref,
        user_id=(auth.user.id if auth.user else None),
    )
    selected_policy = (
        dict(payload.policy)
        if payload.policy
        else dict(TIER_POLICY_PRESETS.get(payload.tier, TIER_POLICY_PRESETS["personal"]))
    )
    pack = PromptPack(
        organization_id=_scope_organization_id(scope=payload.scope, organization_id=ctx.organization.id),
        created_by_user_id=(auth.user.id if auth.user else None),
        scope=payload.scope,
        scope_ref=scope_ref,
        tier=payload.tier,
        pack_key=payload.pack_key,
        version=payload.version,
        description=payload.description,
        policy=selected_policy,
        pack_metadata=dict(payload.metadata),
    )
    session.add(pack)
    await session.flush()

    if payload.set_champion:
        binding, previous_pack_id = await upsert_pack_binding(
            session,
            organization_id=_scope_organization_id(scope=payload.scope, organization_id=ctx.organization.id),
            created_by_user_id=(auth.user.id if auth.user else None),
            scope=payload.scope,
            scope_ref=scope_ref,
            tier=payload.tier,
            pack_key=payload.pack_key,
            champion_pack_id=pack.id,
        )
        await record_promotion_event(
            session,
            organization_id=binding.organization_id,
            binding_id=binding.id,
            event_type="promote",
            from_pack_id=previous_pack_id,
            to_pack_id=pack.id,
            triggered_by_user_id=(auth.user.id if auth.user else None),
            reason="Initial champion binding" if previous_pack_id is None else "Champion updated on create",
            metrics={"forced": True},
        )

    await session.commit()
    await session.refresh(pack)
    return _pack_read_model(pack)


@router.post("/{pack_id}/promote", response_model=PackMutationResponse)
async def promote_pack(
    pack_id: UUID,
    payload: PackPromotionRequest,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> PackMutationResponse:
    """Promote a pack to champion when deterministic gate conditions pass."""
    pack = await PromptPack.objects.by_id(pack_id).first(session)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _assert_pack_visibility(pack=pack, organization_id=ctx.organization.id)

    scope_ref = normalize_scope_ref(
        payload.scope,
        payload.scope_ref,
        user_id=(auth.user.id if auth.user else None),
    )
    scope_organization_id = _scope_organization_id(
        scope=payload.scope,
        organization_id=ctx.organization.id,
    )

    binding = await select_pack_for_scope(
        session,
        scope=payload.scope,
        scope_ref=scope_ref,
        organization_id=scope_organization_id,
        tier=payload.tier,
        pack_key=payload.pack_key,
    )
    previous_pack_id = binding.champion_pack_id if binding is not None else None

    challenger_summary = await eval_summary_for_pack(
        session,
        organization_id=ctx.organization.id,
        pack_id=pack.id,
    )
    champion_summary = None
    if previous_pack_id is not None:
        champion_summary = await eval_summary_for_pack(
            session,
            organization_id=ctx.organization.id,
            pack_id=previous_pack_id,
        )

    if not payload.force:
        if challenger_summary.count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Promotion blocked: challenger has no deterministic evaluations.",
            )

        if payload.require_zero_hard_regressions and challenger_summary.hard_regressions > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Promotion blocked: challenger contains hard regressions.",
            )

        if (
            champion_summary is not None
            and champion_summary.count > 0
            and previous_pack_id is not None
            and previous_pack_id != pack.id
        ):
            threshold = champion_summary.avg_score * (1.0 + payload.min_improvement_pct / 100.0)
            if challenger_summary.avg_score < threshold:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Promotion blocked: challenger does not meet minimum improvement threshold."
                    ),
                )

    binding, previous_pack_id = await upsert_pack_binding(
        session,
        organization_id=scope_organization_id,
        created_by_user_id=(auth.user.id if auth.user else None),
        scope=payload.scope,
        scope_ref=scope_ref,
        tier=payload.tier,
        pack_key=payload.pack_key,
        champion_pack_id=pack.id,
    )

    await record_promotion_event(
        session,
        organization_id=binding.organization_id,
        binding_id=binding.id,
        event_type="promote",
        from_pack_id=previous_pack_id,
        to_pack_id=pack.id,
        triggered_by_user_id=(auth.user.id if auth.user else None),
        reason=payload.reason,
        metrics={
            "forced": payload.force,
            "challenger_eval_count": challenger_summary.count,
            "challenger_avg_score": challenger_summary.avg_score,
            "challenger_hard_regressions": challenger_summary.hard_regressions,
            "champion_avg_score": (champion_summary.avg_score if champion_summary else None),
            "min_improvement_pct": payload.min_improvement_pct,
        },
    )

    await session.commit()
    return PackMutationResponse(
        binding_id=binding.id,
        previous_pack_id=previous_pack_id,
        champion_pack_id=binding.champion_pack_id,
        promoted=True,
    )


@router.post("/{pack_id}/rollback", response_model=PackMutationResponse)
async def rollback_pack(
    pack_id: UUID,
    payload: PackRollbackRequest,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> PackMutationResponse:
    """Rollback champion binding to previous stable pack revision."""
    scope_ref = normalize_scope_ref(
        payload.scope,
        payload.scope_ref,
        user_id=(auth.user.id if auth.user else None),
    )
    scope_organization_id = _scope_organization_id(
        scope=payload.scope,
        organization_id=ctx.organization.id,
    )

    binding = await select_pack_for_scope(
        session,
        scope=payload.scope,
        scope_ref=scope_ref,
        organization_id=scope_organization_id,
        tier=payload.tier,
        pack_key=payload.pack_key,
    )
    if binding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if binding.champion_pack_id != pack_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rollback target mismatch: pack is not the active champion.",
        )

    target_pack_id = payload.target_pack_id
    if target_pack_id is None:
        target_pack_id = await latest_non_current_pack_for_binding(
            session,
            binding_id=binding.id,
            current_pack_id=pack_id,
        )
    if target_pack_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rollback blocked: no previous champion found.",
        )

    target_pack = await PromptPack.objects.by_id(target_pack_id).first(session)
    if target_pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _assert_pack_visibility(pack=target_pack, organization_id=ctx.organization.id)

    updated_binding, previous_pack_id = await upsert_pack_binding(
        session,
        organization_id=scope_organization_id,
        created_by_user_id=(auth.user.id if auth.user else None),
        scope=payload.scope,
        scope_ref=scope_ref,
        tier=payload.tier,
        pack_key=payload.pack_key,
        champion_pack_id=target_pack.id,
    )

    await record_promotion_event(
        session,
        organization_id=updated_binding.organization_id,
        binding_id=updated_binding.id,
        event_type="rollback",
        from_pack_id=previous_pack_id,
        to_pack_id=target_pack.id,
        triggered_by_user_id=(auth.user.id if auth.user else None),
        reason=payload.reason,
        metrics={"rolled_back_from": str(pack_id)},
    )
    await session.commit()

    return PackMutationResponse(
        binding_id=updated_binding.id,
        previous_pack_id=previous_pack_id,
        champion_pack_id=updated_binding.champion_pack_id,
        promoted=False,
    )
