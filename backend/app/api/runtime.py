"""Runtime control-plane routes for telemetry ingestion and pack resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import require_admin_or_agent, require_org_admin
from app.api.runtime_ops import RuntimeControlPlaneStatusRead, runtime_control_plane_status
from app.core.time import utcnow
from app.db.session import get_session
from app.models.boards import Board
from app.models.run_telemetry import RunTelemetry
from app.schemas.control_plane import PackResolutionResponse, RuntimeRunIngestRequest, RuntimeRunIngestResponse
from app.services.control_plane import resolve_pack_binding
from app.services.deterministic_eval_queue import QueuedDeterministicEval, enqueue_deterministic_eval
from app.services.organizations import OrganizationContext, ensure_member_for_user, require_board_access

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.api.deps import ActorContext

router = APIRouter(prefix="/runtime", tags=["control-plane"])
SESSION_DEP = Depends(get_session)
ACTOR_DEP = Depends(require_admin_or_agent)
TIER_QUERY = Query(default="personal")
DOMAIN_QUERY = Query(default="")
PACK_KEY_QUERY = Query(default="engineering-delivery-pack")
PROFILE_QUERY = Query(default="auto")
ORG_ADMIN_DEP = Depends(require_org_admin)


def _normalize_tier(value: str) -> str:
    tier = value.strip().lower()
    if tier not in {"personal", "enterprise"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="tier must be one of: personal, enterprise",
        )
    return tier


async def _runtime_scope(
    *,
    session: AsyncSession,
    actor: ActorContext,
    board_id: UUID | None,
) -> tuple[UUID, UUID | None, UUID | None]:
    if actor.actor_type == "agent":
        if actor.agent is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        effective_board_id = board_id or actor.agent.board_id
        if effective_board_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="board_id is required for agent runtime requests.",
            )
        if actor.agent.board_id and actor.agent.board_id != effective_board_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        board = await Board.objects.by_id(effective_board_id).first(session)
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return board.organization_id, board.id, None

    if actor.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    if board_id is not None:
        board = await Board.objects.by_id(board_id).first(session)
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await require_board_access(session, user=actor.user, board=board, write=False)
        return board.organization_id, board.id, actor.user.id

    member = await ensure_member_for_user(session, actor.user)
    return member.organization_id, None, actor.user.id


@router.post("/runs", response_model=RuntimeRunIngestResponse)
async def ingest_runtime_run(
    payload: RuntimeRunIngestRequest,
    session: AsyncSession = SESSION_DEP,
    actor: ActorContext = ACTOR_DEP,
) -> RuntimeRunIngestResponse:
    """Ingest runtime telemetry and enqueue deterministic evaluation."""
    organization_id, effective_board_id, user_id = await _runtime_scope(
        session=session,
        actor=actor,
        board_id=payload.board_id,
    )

    resolved_pack_id = payload.pack_id
    if resolved_pack_id is None:
        resolved = await resolve_pack_binding(
            session,
            organization_id=organization_id,
            user_id=user_id,
            domain=(payload.domain or "").strip(),
            tier=payload.tier,
            pack_key=payload.pack_key,
        )
        if resolved is not None:
            resolved_pack_id = resolved.pack.id

    run = RunTelemetry(
        organization_id=organization_id,
        board_id=effective_board_id,
        user_id=user_id,
        agent_id=(actor.agent.id if actor.actor_type == "agent" and actor.agent else None),
        task_id=payload.task_id,
        pack_id=resolved_pack_id,
        pack_key=payload.pack_key,
        tier=payload.tier,
        domain=(payload.domain or "").strip(),
        run_ref=(payload.run_ref or "").strip(),
        success_bool=payload.success_bool,
        retries=payload.retries,
        latency_ms=payload.latency_ms,
        format_contract_passed=payload.format_contract_passed,
        approval_gate_passed=payload.approval_gate_passed,
        checks=dict(payload.checks),
        run_metadata=dict(payload.metadata),
        created_at=utcnow(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    queued = enqueue_deterministic_eval(
        QueuedDeterministicEval(
            run_telemetry_id=run.id,
            queued_at=datetime.now(UTC),
        ),
    )
    return RuntimeRunIngestResponse(run_id=run.id, queued_for_eval=queued)


@router.get("/packs/resolve", response_model=PackResolutionResponse)
async def resolve_runtime_pack(
    board_id: UUID | None = None,
    tier: str = TIER_QUERY,
    pack_key: str = PACK_KEY_QUERY,
    domain: str = DOMAIN_QUERY,
    session: AsyncSession = SESSION_DEP,
    actor: ActorContext = ACTOR_DEP,
) -> PackResolutionResponse:
    """Resolve the champion pack for runtime injection under current scope."""
    normalized_tier = _normalize_tier(tier)
    organization_id, _, user_id = await _runtime_scope(
        session=session,
        actor=actor,
        board_id=board_id,
    )
    resolved = await resolve_pack_binding(
        session,
        organization_id=organization_id,
        user_id=user_id,
        domain=domain.strip(),
        tier=normalized_tier,
        pack_key=pack_key.strip() or "engineering-delivery-pack",
    )
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No champion pack binding found for requested scope.",
        )

    pack = resolved.pack
    return PackResolutionResponse(
        binding_id=resolved.binding.id,
        prompt_pack_id=pack.id,
        scope=resolved.binding.scope,
        scope_ref=resolved.binding.scope_ref,
        tier=resolved.binding.tier,
        pack_key=resolved.binding.pack_key,
        version=pack.version,
        policy=pack.policy,
        resolved_chain=resolved.resolved_chain,
    )


@router.get("/control-plane/status", response_model=RuntimeControlPlaneStatusRead)
async def runtime_control_plane_status_alias(
    request: Request,
    board_id: UUID | None = Query(default=None),
    profile: str = PROFILE_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> RuntimeControlPlaneStatusRead:
    """Versioned alias for runtime control-plane status used by newer clients."""
    return await runtime_control_plane_status(
        request=request,
        board_id=board_id,
        profile=profile,
        session=session,
        ctx=ctx,
    )
