from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.tasks import Task
from app.schemas.tasks import TaskRead


def test_task_read_includes_notebook_gate_fields() -> None:
    checked_at = datetime.now(UTC).replace(microsecond=0)
    task = Task(
        board_id=uuid4(),
        title="Notebook gate task",
        task_mode="notebook",
        notebook_gate_state="misconfig",
        notebook_gate_reason="invalid_profile",
        notebook_gate_checked_at=checked_at,
    )

    payload = TaskRead.model_validate(task, from_attributes=True).model_dump(mode="json")

    assert payload["notebook_gate_state"] == "misconfig"
    assert payload["notebook_gate_reason"] == "invalid_profile"
    assert payload["notebook_gate_checked_at"] == checked_at.isoformat().replace("+00:00", "Z")


def test_task_read_defaults_notebook_gate_fields_to_none() -> None:
    task = Task(board_id=uuid4(), title="Notebook gate default")

    payload = TaskRead.model_validate(task, from_attributes=True).model_dump(mode="json")

    assert payload["notebook_gate_state"] is None
    assert payload["notebook_gate_reason"] is None
    assert payload["notebook_gate_checked_at"] is None
