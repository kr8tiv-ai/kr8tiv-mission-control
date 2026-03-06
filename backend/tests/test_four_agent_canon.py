# ruff: noqa: S101
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.models.agents import Agent
import app.services.openclaw.four_agent_canon as four_agent_canon
from app.services.runtime import verification_harness


def _write_json_yaml(path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_load_persona_canon_rejects_unknown_agents(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("friday", "arsenal", "jocasta", "edith"):
        _write_json_yaml(
            tmp_path / f"{name}.yaml",
            {
                "agent": name,
                "identity_core": {
                    "role": f"{name}-role",
                    "communication_style": "direct",
                    "emoji": ":x:",
                },
            },
        )
    _write_json_yaml(
        tmp_path / "rogue.yaml",
        {
            "agent": "rogue",
            "identity_core": {
                "role": "rogue",
                "communication_style": "direct",
                "emoji": ":x:",
            },
        },
    )

    four_agent_canon.clear_canon_caches()
    monkeypatch.setattr(four_agent_canon, "_canon_root", lambda: tmp_path)

    with pytest.raises(ValueError, match="Unknown agent"):
        _ = four_agent_canon.load_persona_canon()



def test_harness_config_requires_full_15_point_matrix(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_json_yaml(
        tmp_path / "harness.yaml",
        {
            "agents": ["friday", "arsenal", "jocasta", "edith"],
            "points": [
                {
                    "point_id": 1,
                    "name": "IDENTITY_REGISTER",
                    "agent_expectations": {
                        "friday": {},
                        "arsenal": {},
                        "jocasta": {},
                        "edith": {},
                    },
                }
            ],
        },
    )

    four_agent_canon.clear_canon_caches()
    monkeypatch.setattr(four_agent_canon, "_harness_path", lambda: tmp_path / "harness.yaml")

    with pytest.raises(ValueError, match="point_id 1..15"):
        _ = four_agent_canon.load_four_agent_harness()



def test_canonical_identity_profile_enforces_supermemory_default() -> None:
    four_agent_canon.clear_canon_caches()
    for name in four_agent_canon.target_agent_names():
        profile = four_agent_canon.canonical_identity_profile(name)
        assert profile["memory_backend"] == "supermemory"
        assert profile["memory_policy"] == "supermemory-only"
        assert profile["tools_profile"] == "coding"
        assert profile["tailscale_access"] == "required_on_spawn"
        assert profile["host_context_bootstrap"] == "required_on_spawn"
        assert profile["identity_bootstrap"] == "required_on_spawn"



def test_render_identity_template_contains_role_sections() -> None:
    four_agent_canon.clear_canon_caches()
    for name in four_agent_canon.target_agent_names():
        markdown = four_agent_canon.render_identity_template(name)
        assert "# IDENTITY.md" in markdown
        assert "## Canonical Identity" in markdown
        assert "## Spawn Requirements" in markdown
        assert "## Memory Policy" in markdown



def test_point3_fails_when_memory_backend_not_supermemory() -> None:
    agent = Agent(
        id=uuid4(),
        board_id=None,
        gateway_id=uuid4(),
        name="friday",
        identity_profile={"memory_backend": "local", "memory_policy": "local-first"},
    )
    point = {
        "point_id": 3,
        "name": "MEMORY_BIND",
        "agent_expectations": {
            "friday": {"memory_backend": "supermemory", "memory_policy": "supermemory-only"}
        },
    }

    result = verification_harness._evaluate_agent_point(agent=agent, point=point)
    assert result.passed is False
    assert result.evidence_ref == "identity_profile.memory_backend+memory_policy+memory_container_tag"


def test_point4_fails_when_model_transport_drifts() -> None:
    agent = Agent(
        id=uuid4(),
        board_id=None,
        gateway_id=uuid4(),
        name="arsenal",
        model_policy={
            "provider": "codex-cli",
            "model": "codex-cli/gpt-5.4",
            "transport": "api",
            "locked": True,
            "allow_self_change": False,
        },
    )
    point = {
        "point_id": 4,
        "name": "MODEL_ROUTE",
        "agent_expectations": {
            "arsenal": {
                "model": "codex-cli/gpt-5.4",
                "transport": "cli",
                "locked": True,
            }
        },
    }

    result = verification_harness._evaluate_agent_point(agent=agent, point=point)
    assert result.passed is False
    assert result.evidence_ref == "model_policy.model+transport+locked+agent_continuity.runtime_session_id"


def test_point6_fails_when_spawn_requirements_missing() -> None:
    agent = Agent(
        id=uuid4(),
        board_id=None,
        gateway_id=uuid4(),
        name="friday",
        identity_profile={
            "assignment_authority": "owner_or_friday",
            "tools_profile": "messaging",
            "tailscale_access": "",
            "host_context_bootstrap": "",
            "identity_bootstrap": "",
        },
    )
    point = {
        "point_id": 6,
        "name": "TASK_INTAKE",
        "agent_expectations": {
            "friday": {
                "assignment_authority": "owner_or_friday",
                "tools_profile": "coding",
                "tailscale_access": "required_on_spawn",
                "host_context_bootstrap": "required_on_spawn",
                "identity_bootstrap": "required_on_spawn",
            }
        },
    }

    result = verification_harness._evaluate_agent_point(agent=agent, point=point)
    assert result.passed is False
    assert result.evidence_ref == (
        "identity_profile.assignment_authority+tools_profile+tailscale_access+"
        "host_context_bootstrap+identity_bootstrap+agent_continuity.runtime_session_id"
    )
