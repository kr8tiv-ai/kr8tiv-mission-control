"""Runtime NotebookLM capability-gate endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_org_admin
from app.schemas.notebook_ops import NotebookCapabilityGateRead
from app.services.notebooklm_capability_gate import evaluate_notebooklm_capability
from app.services.organizations import OrganizationContext

router = APIRouter(prefix="/runtime/notebook", tags=["control-plane"])
ORG_ADMIN_DEP = Depends(require_org_admin)


@router.get("/gate", response_model=NotebookCapabilityGateRead)
async def get_notebook_capability_gate(
    profile: str = Query(default="auto"),
    notebook_id: str | None = Query(default=None),
    require_notebook: bool = Query(default=False),
    _ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> NotebookCapabilityGateRead:
    """Return current NotebookLM capability gate status for requested query context."""
    result = await evaluate_notebooklm_capability(
        profile=profile,
        notebook_id=notebook_id,
        require_notebook=require_notebook,
    )
    return NotebookCapabilityGateRead(
        state=result.state,
        reason=result.reason,
        operator_message=result.operator_message,
        checked_at=result.checked_at,
        selected_profile=result.selected_profile,
        notebook_count=result.notebook_count,
    )

