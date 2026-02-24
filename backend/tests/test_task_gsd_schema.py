from __future__ import annotations

from app.schemas.tasks import TaskCreate


def test_task_create_accepts_gsd_stage_and_deployment_mode() -> None:
    payload = TaskCreate.model_validate(
        {
            "title": "Test task",
            "task_mode": "standard",
            "gsd_stage": "spec",
            "deployment_mode": "individual",
            "owner_approval_required": True,
        }
    )
    assert payload.gsd_stage == "spec"
    assert payload.deployment_mode == "individual"
    assert payload.owner_approval_required is True
