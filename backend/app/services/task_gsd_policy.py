"""GSD stage transition policy for task lifecycle gating."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GSDTransitionResult:
    ok: bool
    reason: str | None = None
    fallback_stage: str | None = None


_STAGE_ORDER = {
    "spec": 0,
    "plan": 1,
    "execute": 2,
    "verify": 3,
    "done": 4,
}


def validate_transition(
    *,
    current_stage: str,
    target_stage: str,
    deployment_mode: str,
    owner_approval_required: bool,
    owner_approved: bool,
    has_spec: bool,
    has_plan: bool,
) -> GSDTransitionResult:
    """Validate requested GSD transition against required guards."""
    source = (current_stage or "spec").strip().lower()
    target = (target_stage or source).strip().lower()
    mode = (deployment_mode or "team").strip().lower()

    if source not in _STAGE_ORDER or target not in _STAGE_ORDER:
        return GSDTransitionResult(
            ok=False,
            reason=f"Unknown gsd_stage transition: {source} -> {target}",
            fallback_stage=source,
        )

    if _STAGE_ORDER[target] > _STAGE_ORDER[source] + 1:
        return GSDTransitionResult(
            ok=False,
            reason=f"Invalid gsd_stage jump: {source} -> {target}",
            fallback_stage=source,
        )

    if target == "execute":
        if not has_spec:
            return GSDTransitionResult(
                ok=False,
                reason="Cannot enter execute stage without spec_doc_ref.",
                fallback_stage="plan",
            )
        if not has_plan:
            return GSDTransitionResult(
                ok=False,
                reason="Cannot enter execute stage without plan_doc_ref.",
                fallback_stage="plan",
            )

    if mode == "individual" and owner_approval_required and target in {"execute", "verify", "done"}:
        if not owner_approved:
            return GSDTransitionResult(
                ok=False,
                reason="Owner approval is required for high-risk individual-mode transitions.",
                fallback_stage="plan",
            )

    return GSDTransitionResult(ok=True)
