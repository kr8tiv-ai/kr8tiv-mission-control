# ruff: noqa: S101
from __future__ import annotations

from app.services.task_mode_queue import is_skill_route_eligible


def test_is_skill_route_eligible_allows_legacy_skills_without_ingest_status() -> None:
    assert is_skill_route_eligible(None) is True
    assert is_skill_route_eligible({}) is True
    assert is_skill_route_eligible({"source": "legacy"}) is True
    assert is_skill_route_eligible({"ingest_status": ""}) is True


def test_is_skill_route_eligible_blocks_explicit_non_accepted_status() -> None:
    assert is_skill_route_eligible({"ingest_status": "accepted"}) is True
    assert is_skill_route_eligible({"ingest_status": "quarantined"}) is False
