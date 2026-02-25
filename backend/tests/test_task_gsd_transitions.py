from __future__ import annotations

from app.services.task_gsd_policy import validate_transition


def test_execute_blocked_without_spec_and_plan() -> None:
    result = validate_transition(
        current_stage="plan",
        target_stage="execute",
        deployment_mode="individual",
        owner_approval_required=True,
        owner_approved=False,
        has_spec=False,
        has_plan=True,
    )
    assert result.ok is False
    assert result.reason is not None
    assert "spec" in result.reason.lower()
    assert result.fallback_stage == "plan"


def test_individual_high_risk_requires_owner_approval() -> None:
    result = validate_transition(
        current_stage="plan",
        target_stage="execute",
        deployment_mode="individual",
        owner_approval_required=True,
        owner_approved=False,
        has_spec=True,
        has_plan=True,
    )
    assert result.ok is False
    assert result.reason is not None
    assert "owner approval" in result.reason.lower()


def test_execute_allowed_when_prereqs_and_approval_are_satisfied() -> None:
    result = validate_transition(
        current_stage="plan",
        target_stage="execute",
        deployment_mode="individual",
        owner_approval_required=True,
        owner_approved=True,
        has_spec=True,
        has_plan=True,
    )
    assert result.ok is True
