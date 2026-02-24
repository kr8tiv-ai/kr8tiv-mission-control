"""API routes for prompt evolution registry, versioning, and promotion gates."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select

from app.api.deps import get_board_for_actor_read, get_board_for_user_write, require_admin_auth
from app.db.session import get_session
from app.models.boards import Board
from app.models.prompt_evolution import PromotionEvent, PromptPack, PromptVersion, TaskEvalScore
from app.schemas.prompt_evolution import (
    PromotionEventRead,
    PromotionRequest,
    PromptPackCreate,
    PromptPackRead,
    PromptVersionCreate,
    PromptVersionRead,
    TaskEvalScoreRead,
)

if False:  # pragma: no cover
    from app.core.auth import AuthContext
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/boards/{board_id}/prompt-evolution", tags=["prompt-evolution"])


@router.get("/packs", response_model=list[PromptPackRead])
async def list_prompt_packs(
    board: Board = Depends(get_board_for_actor_read),
    session: AsyncSession = Depends(get_session),
) -> list[PromptPackRead]:
    rows = list(
        await session.exec(
            select(PromptPack)
            .where(col(PromptPack.board_id) == board.id)
            .order_by(col(PromptPack.created_at).desc()),
        ),
    )
    return [PromptPackRead.model_validate(row, from_attributes=True) for row in rows]


@router.post("/packs", response_model=PromptPackRead, status_code=status.HTTP_201_CREATED)
async def create_prompt_pack(
    payload: PromptPackCreate,
    board: Board = Depends(get_board_for_user_write),
    session: AsyncSession = Depends(get_session),
    _auth: AuthContext = Depends(require_admin_auth),
) -> PromptPackRead:
    pack = PromptPack(
        board_id=board.id,
        name=payload.name.strip(),
        scope=payload.scope.strip().lower(),
        target_agent_id=payload.target_agent_id,
    )
    session.add(pack)
    await session.commit()
    await session.refresh(pack)
    return PromptPackRead.model_validate(pack, from_attributes=True)


@router.get("/packs/{pack_id}/versions", response_model=list[PromptVersionRead])
async def list_prompt_versions(
    pack_id: UUID,
    board: Board = Depends(get_board_for_actor_read),
    session: AsyncSession = Depends(get_session),
) -> list[PromptVersionRead]:
    pack = await session.get(PromptPack, pack_id)
    if pack is None or pack.board_id != board.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    rows = list(
        await session.exec(
            select(PromptVersion)
            .where(col(PromptVersion.prompt_pack_id) == pack.id)
            .order_by(col(PromptVersion.version_number).desc()),
        ),
    )
    return [PromptVersionRead.model_validate(row, from_attributes=True) for row in rows]


@router.post(
    "/packs/{pack_id}/versions",
    response_model=PromptVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_prompt_version(
    pack_id: UUID,
    payload: PromptVersionCreate,
    board: Board = Depends(get_board_for_user_write),
    session: AsyncSession = Depends(get_session),
    _auth: AuthContext = Depends(require_admin_auth),
) -> PromptVersionRead:
    pack = await session.get(PromptPack, pack_id)
    if pack is None or pack.board_id != board.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    max_version = (
        await session.exec(
            select(PromptVersion.version_number)
            .where(col(PromptVersion.prompt_pack_id) == pack.id)
            .order_by(col(PromptVersion.version_number).desc())
            .limit(1),
        )
    ).first()
    next_version = (max_version or 0) + 1

    version = PromptVersion(
        prompt_pack_id=pack.id,
        version_number=next_version,
        instruction_text=payload.instruction_text,
        context_payload=dict(payload.context_payload),
        metrics_payload=dict(payload.metrics_payload),
    )
    session.add(version)
    await session.flush()

    if pack.champion_version_id is None:
        pack.champion_version_id = version.id
    elif payload.set_as_challenger:
        pack.challenger_version_id = version.id
    pack.updated_at = version.created_at
    session.add(pack)

    await session.commit()
    await session.refresh(version)
    return PromptVersionRead.model_validate(version, from_attributes=True)


@router.post("/packs/{pack_id}/promote", response_model=PromotionEventRead)
async def promote_challenger(
    pack_id: UUID,
    payload: PromotionRequest,
    board: Board = Depends(get_board_for_user_write),
    session: AsyncSession = Depends(get_session),
    _auth: AuthContext = Depends(require_admin_auth),
) -> PromotionEventRead:
    pack = await session.get(PromptPack, pack_id)
    if pack is None or pack.board_id != board.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    to_version = await session.get(PromptVersion, payload.to_version_id)
    if to_version is None or to_version.prompt_pack_id != pack.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="to_version_id must belong to the same prompt pack.",
        )

    event = PromotionEvent(
        board_id=board.id,
        prompt_pack_id=pack.id,
        from_version_id=pack.champion_version_id,
        to_version_id=to_version.id,
        decision="approved",
        reason=payload.reason,
    )
    pack.champion_version_id = to_version.id
    if pack.challenger_version_id == to_version.id:
        pack.challenger_version_id = None
    session.add(pack)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return PromotionEventRead.model_validate(event, from_attributes=True)


@router.get("/task-evals", response_model=list[TaskEvalScoreRead])
async def list_task_eval_scores(
    board: Board = Depends(get_board_for_actor_read),
    session: AsyncSession = Depends(get_session),
) -> list[TaskEvalScoreRead]:
    rows = list(
        await session.exec(
            select(TaskEvalScore)
            .where(col(TaskEvalScore.board_id) == board.id)
            .order_by(col(TaskEvalScore.created_at).desc())
            .limit(200),
        ),
    )
    return [TaskEvalScoreRead.model_validate(row, from_attributes=True) for row in rows]
