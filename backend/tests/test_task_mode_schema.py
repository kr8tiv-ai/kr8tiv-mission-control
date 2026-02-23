from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.tasks import ArenaConfig, NotebookSources, TaskCreate


def test_task_create_arena_requires_arena_config() -> None:
    with pytest.raises(ValidationError, match="arena_config is required for arena task modes"):
        TaskCreate(title="Arena task", task_mode="arena")


def test_task_create_notebook_creation_requires_sources() -> None:
    with pytest.raises(ValidationError, match="requires at least one source URL or text snippet"):
        TaskCreate(
            title="Notebook creation task",
            task_mode="notebook_creation",
            arena_config=ArenaConfig(sources=NotebookSources(urls=[], texts=[])),
        )


def test_task_create_notebook_creation_accepts_urls_or_text() -> None:
    task = TaskCreate(
        title="Notebook creation task",
        task_mode="notebook_creation",
        arena_config=ArenaConfig(
            sources=NotebookSources(urls=["https://example.com"], texts=[]),
        ),
    )
    assert task.task_mode == "notebook_creation"
