from __future__ import annotations

from uuid import uuid4

from app.api import tasks as tasks_api
from app.models.agents import Agent


def _agent(
    *,
    name: str,
    is_board_lead: bool = False,
    openclaw_session_id: str | None = None,
) -> Agent:
    return Agent(
        id=uuid4(),
        board_id=uuid4(),
        gateway_id=uuid4(),
        name=name,
        is_board_lead=is_board_lead,
        openclaw_session_id=openclaw_session_id,
    )


def test_resolve_task_manager_prefers_friday_with_session() -> None:
    friday = _agent(
        name="Friday",
        is_board_lead=False,
        openclaw_session_id="agent:friday:session",
    )
    lead = _agent(
        name="Lead Agent",
        is_board_lead=True,
        openclaw_session_id="agent:lead:session",
    )

    resolution = tasks_api._resolve_task_manager_from_agents([lead, friday])

    assert resolution.agent is friday
    assert resolution.source == "friday"
    assert resolution.reason is None


def test_resolve_task_manager_falls_back_to_board_lead_when_friday_missing() -> None:
    worker = _agent(
        name="Arsenal",
        is_board_lead=False,
        openclaw_session_id="agent:arsenal:session",
    )
    lead = _agent(
        name="Lead Agent",
        is_board_lead=True,
        openclaw_session_id="agent:lead:session",
    )

    resolution = tasks_api._resolve_task_manager_from_agents([worker, lead])

    assert resolution.agent is lead
    assert resolution.source == "board_lead"
    assert resolution.reason is None


def test_resolve_task_manager_reports_skip_reason_when_no_routable_manager() -> None:
    friday_without_session = _agent(
        name="Friday",
        is_board_lead=False,
        openclaw_session_id=None,
    )
    lead_without_session = _agent(
        name="Lead Agent",
        is_board_lead=True,
        openclaw_session_id=None,
    )

    resolution = tasks_api._resolve_task_manager_from_agents(
        [friday_without_session, lead_without_session],
    )

    assert resolution.agent is None
    assert resolution.source == "none"
    assert resolution.reason == "friday_missing_session"
