"""Four-agent canonical persona + harness policy utilities."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID

from sqlmodel import select

from app.core.time import utcnow
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.persona_presets import PersonaPreset
from app.services.openclaw.model_policy import enforce_agent_model_policy
from app.services.openclaw.persona_integrity_service import PersonaIntegrityService

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

TARGET_AGENT_NAMES: Final[tuple[str, ...]] = ("friday", "arsenal", "jocasta", "edith")
_TARGET_AGENT_SET: Final[frozenset[str]] = frozenset(TARGET_AGENT_NAMES)
_CANON_VERSION: Final[str] = "canon-v1"


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _canon_root() -> Path:
    return _backend_root() / "config" / "persona_canon"


def _harness_path() -> Path:
    return _backend_root() / "config" / "four_agent_harness.v1.yaml"


def _normalize_agent_name(name: object) -> str:
    return str(name or "").strip().lower()


def _parse_yaml_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        msg = f"Empty canonical contract file: {path}"
        raise ValueError(msg)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"Canonical contract file is not JSON-compatible YAML: {path}"
        raise ValueError(msg) from exc
    if not isinstance(parsed, dict):
        msg = f"Canonical contract root must be an object: {path}"
        raise ValueError(msg)
    return parsed


def target_agent_names() -> tuple[str, ...]:
    return TARGET_AGENT_NAMES


def is_target_agent(name: object) -> bool:
    return _normalize_agent_name(name) in _TARGET_AGENT_SET


@lru_cache(maxsize=1)
def load_persona_canon() -> dict[str, dict[str, Any]]:
    """Load and validate four-agent persona canon files from disk."""
    canon_dir = _canon_root()
    docs: dict[str, dict[str, Any]] = {}
    for file_path in sorted(canon_dir.glob("*.yaml")):
        payload = _parse_yaml_json(file_path)
        agent_name = _normalize_agent_name(payload.get("agent"))
        if not agent_name:
            msg = f"Missing `agent` field in persona canon file: {file_path.name}"
            raise ValueError(msg)
        if agent_name not in _TARGET_AGENT_SET:
            msg = (
                f"Unknown agent `{agent_name}` in persona canon. "
                f"Only {', '.join(TARGET_AGENT_NAMES)} are allowed."
            )
            raise ValueError(msg)
        docs[agent_name] = payload

    missing = [name for name in TARGET_AGENT_NAMES if name not in docs]
    if missing:
        msg = f"Missing persona canon files for: {', '.join(missing)}"
        raise ValueError(msg)

    return docs


@lru_cache(maxsize=1)
def load_four_agent_harness() -> dict[str, Any]:
    """Load and validate the four-agent 15-point harness config."""
    payload = _parse_yaml_json(_harness_path())

    raw_agents = payload.get("agents")
    if not isinstance(raw_agents, list):
        raise ValueError("four_agent_harness agents must be a list")
    normalized_agents = [_normalize_agent_name(name) for name in raw_agents]
    if set(normalized_agents) != _TARGET_AGENT_SET:
        raise ValueError("four_agent_harness agents must match friday/arsenal/jocasta/edith exactly")

    points = payload.get("points")
    if not isinstance(points, list):
        raise ValueError("four_agent_harness points must be a list")

    point_ids: set[int] = set()
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("each harness point must be an object")
        point_id = point.get("point_id")
        if not isinstance(point_id, int):
            raise ValueError("each harness point requires integer point_id")
        point_ids.add(point_id)
        expectations = point.get("agent_expectations")
        if not isinstance(expectations, dict):
            raise ValueError(f"point {point_id} missing agent_expectations object")
        normalized_keys = {_normalize_agent_name(name) for name in expectations.keys()}
        if normalized_keys != _TARGET_AGENT_SET:
            raise ValueError(
                f"point {point_id} must define expectations for friday/arsenal/jocasta/edith"
            )

    if point_ids != set(range(1, 16)):
        raise ValueError("harness must include exactly point_id 1..15")

    return payload


def clear_canon_caches() -> None:
    load_persona_canon.cache_clear()
    load_four_agent_harness.cache_clear()


def _lines_to_markdown(lines: list[str]) -> str:
    rows = [str(line).strip() for line in lines if str(line).strip()]
    if not rows:
        return "- (none)"
    return "\n".join(f"- {row}" for row in rows)


def _canon_for(agent_name: str) -> dict[str, Any]:
    key = _normalize_agent_name(agent_name)
    docs = load_persona_canon()
    if key not in docs:
        raise ValueError(f"Unknown canonical agent: {agent_name}")
    return docs[key]


def render_identity_template(agent_name: str) -> str:
    """Render canonical IDENTITY.md content for one target agent."""
    canon = _canon_for(agent_name)
    identity = canon.get("identity_core") or {}
    role = str(identity.get("role") or "").strip()
    style = str(identity.get("communication_style") or "").strip()
    emoji = str(identity.get("emoji") or "").strip()
    spawn = canon.get("spawn_requirements") or {}

    return (
        "# IDENTITY.md\n\n"
        "## Canonical Identity\n"
        f"- Name: {str(canon.get('agent') or '').title()}\n"
        f"- Role: {role}\n"
        f"- Communication Style: {style}\n"
        f"- Emoji: {emoji}\n"
        f"- Canon Version: {_CANON_VERSION}\n\n"
        "## Personality And Tone\n"
        f"{_lines_to_markdown(list(canon.get('personality_tone') or []))}\n\n"
        "## Scope\n"
        f"{_lines_to_markdown(list(canon.get('scope') or []))}\n\n"
        "## Out Of Scope\n"
        f"{_lines_to_markdown(list(canon.get('out_of_scope') or []))}\n\n"
        "## Escalation Behavior\n"
        f"{_lines_to_markdown(list(canon.get('escalation_behavior') or []))}\n\n"
        "## Coordination Rules\n"
        f"{_lines_to_markdown(list(canon.get('coordination_rules') or []))}\n\n"
        "## Spawn Requirements\n"
        f"- Tailscale Access: {str(spawn.get('tailscale_access') or 'required_on_spawn').strip()}\n"
        f"- Host Context Bootstrap: {str(spawn.get('host_context_bootstrap') or 'required_on_spawn').strip()}\n"
        f"- Identity Bootstrap: {str(spawn.get('identity_bootstrap') or 'required_on_spawn').strip()}\n"
        f"{_lines_to_markdown(list(spawn.get('notes') or []))}\n\n"
        "## Memory Policy\n"
        f"- Backend: {str((canon.get('memory_rules') or {}).get('backend') or '').strip()}\n"
        f"- Policy: {str((canon.get('memory_rules') or {}).get('policy') or '').strip()}\n"
        f"- Container Tag: {str((canon.get('memory_rules') or {}).get('container_tag') or '').strip()}\n"
        f"{_lines_to_markdown(list((canon.get('memory_rules') or {}).get('notes') or []))}\n"
    ).strip()


def render_soul_template(agent_name: str) -> str:
    """Render canonical SOUL.md content for one target agent."""
    canon = _canon_for(agent_name)
    role = str((canon.get("identity_core") or {}).get("role") or "").strip()
    return (
        "# SOUL.md\n\n"
        f"You are {str(canon.get('agent') or '').title()}, the {role}.\n"
        "You are a stateful teammate inside KR8TIV runtime operations.\n\n"
        "## Immutable Core\n"
        "- Supermemory-only memory backend for runtime persistence.\n"
        "- Tailscale access and host-context bootstrap are required at spawn.\n"
        "- Friday/owner assignment authority governs execution starts.\n"
        "- Coordination guidance across peers is allowed; autonomous task takeover is not.\n"
        "- Evidence and verification are mandatory before claiming completion.\n\n"
        "## Personality And Tone\n"
        f"{_lines_to_markdown(list(canon.get('personality_tone') or []))}\n\n"
        "## Execution Principles\n"
        "- Minimal patch first, then validate, then iterate.\n"
        "- Keep outputs concrete, testable, and rollback-safe.\n"
        "- Protect continuity and avoid policy drift.\n"
    ).strip()


def render_heartbeat_contract(agent_name: str) -> str:
    canon = _canon_for(agent_name)
    return _lines_to_markdown(list(canon.get("heartbeat_expectations") or []))


def render_coordination_contract(agent_name: str) -> str:
    canon = _canon_for(agent_name)
    return _lines_to_markdown(list(canon.get("coordination_rules") or []))


def render_escalation_contract(agent_name: str) -> str:
    canon = _canon_for(agent_name)
    return _lines_to_markdown(list(canon.get("escalation_behavior") or []))


def canonical_identity_profile(agent_name: str) -> dict[str, str]:
    canon = _canon_for(agent_name)
    identity = canon.get("identity_core") or {}
    memory_rules = canon.get("memory_rules") or {}
    spawn_rules = canon.get("spawn_requirements") or {}
    scope_lines = _lines_to_markdown(list(canon.get("scope") or []))
    out_of_scope_lines = _lines_to_markdown(list(canon.get("out_of_scope") or []))
    personality = _lines_to_markdown(list(canon.get("personality_tone") or []))

    return {
        "role": str(identity.get("role") or "").strip(),
        "communication_style": str(identity.get("communication_style") or "").strip(),
        "emoji": str(identity.get("emoji") or "").strip(),
        "purpose": scope_lines,
        "personality": personality,
        "custom_instructions": (
            "Coordinate through Friday. Give peer suggestions freely, but only execute when assigned by "
            "Friday or owner."
        ),
        "coordination_contract": render_coordination_contract(agent_name),
        "escalation_contract": render_escalation_contract(agent_name),
        "heartbeat_contract": render_heartbeat_contract(agent_name),
        "memory_backend": str(memory_rules.get("backend") or "").strip(),
        "memory_policy": str(memory_rules.get("policy") or "").strip(),
        "memory_container_tag": str(memory_rules.get("container_tag") or "").strip(),
        "tools_profile": "coding",
        "tailscale_access": str(spawn_rules.get("tailscale_access") or "required_on_spawn").strip(),
        "host_context_bootstrap": str(
            spawn_rules.get("host_context_bootstrap") or "required_on_spawn"
        ).strip(),
        "identity_bootstrap": str(spawn_rules.get("identity_bootstrap") or "required_on_spawn").strip(),
        "spawn_contract": _lines_to_markdown(list(spawn_rules.get("notes") or [])),
        "assignment_authority": "owner_or_friday",
        "context_budget": "0.35",
        "group_channel": "planning_hq",
        "scope_contract": scope_lines,
        "out_of_scope_contract": out_of_scope_lines,
        "self_improvement": "mirror_test=03:00 confidence>0.85",
        "audit_contract": (
            "timestamp,bot_id,action_type,input_hash,output_hash,model_used,tokens_consumed,latency_ms"
        ),
        "halt_contract": "halt_within_seconds=1",
        "hot_reload_contract": "enabled",
        "version_sync_contract": "enabled",
    }


def canonical_preset_key(agent_name: str) -> str:
    return f"{_normalize_agent_name(agent_name)}-{_CANON_VERSION}"


def apply_canon_to_agent(agent: Agent) -> bool:
    """Apply canonical profile/templates to one target agent row."""
    if not is_target_agent(agent.name):
        return False

    canonical_profile = canonical_identity_profile(str(agent.name))
    current_profile = dict(agent.identity_profile or {})
    changed = False

    for key, value in canonical_profile.items():
        if str(current_profile.get(key, "")).strip() != value:
            current_profile[key] = value
            changed = True

    if agent.identity_profile != current_profile:
        agent.identity_profile = current_profile
        changed = True

    identity_template = render_identity_template(str(agent.name))
    if (agent.identity_template or "").strip() != identity_template:
        agent.identity_template = identity_template
        changed = True

    soul_template = render_soul_template(str(agent.name))
    if (agent.soul_template or "").strip() != soul_template:
        agent.soul_template = soul_template
        changed = True

    if changed:
        agent.updated_at = utcnow()

    return changed


async def _resolve_agent_organization_id(session: AsyncSession, agent: Agent) -> UUID | None:
    if agent.board_id is not None:
        board = await Board.objects.by_id(agent.board_id).first(session)
        if board is not None:
            return board.organization_id

    gateway = await Gateway.objects.by_id(agent.gateway_id).first(session)
    if gateway is None:
        return None
    return gateway.organization_id


async def sync_four_agent_canon(session: AsyncSession) -> dict[str, int]:
    """Seed four-agent presets and enforce canonical profile/templates on live rows."""
    rows = (await session.exec(select(Agent))).all()

    targets = [row for row in rows if is_target_agent(row.name)]
    if not targets:
        return {"agents_updated": 0, "presets_upserted": 0, "baseline_resets": 0}

    agents_updated = 0
    presets_upserted = 0
    baseline_resets = 0

    persona_service = PersonaIntegrityService(session)

    for agent in targets:
        org_id = await _resolve_agent_organization_id(session, agent)
        if org_id is None:
            continue

        if enforce_agent_model_policy(agent):
            session.add(agent)
            agents_updated += 1

        if apply_canon_to_agent(agent):
            session.add(agent)
            agents_updated += 1

        preset_key = canonical_preset_key(str(agent.name))
        preset = await PersonaPreset.objects.filter_by(
            organization_id=org_id,
            key=preset_key,
        ).first(session)

        identity_profile = canonical_identity_profile(str(agent.name))
        identity_template = render_identity_template(str(agent.name))
        soul_template = render_soul_template(str(agent.name))

        if preset is None:
            preset = PersonaPreset(
                organization_id=org_id,
                key=preset_key,
                name=f"{str(agent.name).title()} Canon V1",
                description="Four-agent canonical persona contract",
                deployment_mode="team",
                identity_profile=identity_profile,
                identity_template=identity_template,
                soul_template=soul_template,
                metadata_={
                    "agent": _normalize_agent_name(agent.name),
                    "version": _CANON_VERSION,
                    "memory_backend": "supermemory",
                    "memory_policy": "supermemory-only",
                },
            )
            session.add(preset)
            presets_upserted += 1
        else:
            changed = False
            if preset.name != f"{str(agent.name).title()} Canon V1":
                preset.name = f"{str(agent.name).title()} Canon V1"
                changed = True
            if (preset.description or "") != "Four-agent canonical persona contract":
                preset.description = "Four-agent canonical persona contract"
                changed = True
            if preset.deployment_mode != "team":
                preset.deployment_mode = "team"
                changed = True
            if preset.identity_profile != identity_profile:
                preset.identity_profile = identity_profile
                changed = True
            if (preset.identity_template or "").strip() != identity_template:
                preset.identity_template = identity_template
                changed = True
            if (preset.soul_template or "").strip() != soul_template:
                preset.soul_template = soul_template
                changed = True
            desired_metadata = {
                "agent": _normalize_agent_name(agent.name),
                "version": _CANON_VERSION,
                "memory_backend": "supermemory",
                "memory_policy": "supermemory-only",
            }
            if dict(preset.metadata_ or {}) != desired_metadata:
                preset.metadata_ = desired_metadata
                changed = True
            if changed:
                preset.updated_at = utcnow()
                session.add(preset)
                presets_upserted += 1

        await persona_service.reset_baseline(
            agent_id=agent.id,
            file_contents={
                "SOUL.md": soul_template,
                "IDENTITY.md": identity_template,
                "HEARTBEAT.md": render_heartbeat_contract(str(agent.name)),
                "AGENTS.md": render_coordination_contract(str(agent.name)),
            },
        )
        baseline_resets += 1

    await session.commit()
    return {
        "agents_updated": agents_updated,
        "presets_upserted": presets_upserted,
        "baseline_resets": baseline_resets,
    }
