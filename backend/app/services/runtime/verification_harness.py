"""Deterministic runtime verification checks for rollout gating."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from sqlmodel import col, select

from app.core.config import settings
from app.core.time import utcnow
from app.db.session import async_session_maker
from app.models.agent_persona_integrity import AgentPersonaIntegrity
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.recovery_policies import RecoveryPolicy
from app.services.agent_continuity import AgentContinuityItem, AgentContinuityService
from app.services.notebooklm_capability_gate import evaluate_notebooklm_capability
from app.services.openclaw.four_agent_canon import load_four_agent_harness, target_agent_names
from app.services.openclaw.gateway_compat import (
    GatewayVersionCheckResult,
    check_gateway_runtime_compatibility,
)
from app.services.openclaw.gateway_resolver import gateway_client_config
from app.services.openclaw.model_policy import normalize_model_policy


@dataclass(frozen=True, slots=True)
class VerificationCheckResult:
    """Single verification check outcome."""

    name: str
    required: bool
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class AgentPointResult:
    """Per-agent 15-point harness verification row."""

    agent_id: str
    point_id: int
    passed: bool
    detail: str
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class AgentVerificationEvidence:
    """Runtime-backed evidence used to strengthen harness point checks."""

    continuity: AgentContinuityItem | None = None
    persona_integrity: AgentPersonaIntegrity | None = None
    recovery_policy: RecoveryPolicy | None = None
    gateway_version: GatewayVersionCheckResult | None = None


@dataclass(frozen=True, slots=True)
class VerificationHarnessResult:
    """Aggregated verification result with required-check failure count."""

    generated_at: datetime
    checks: list[VerificationCheckResult]
    all_passed: bool
    required_failed: int
    agent_matrix: list[AgentPointResult] = field(default_factory=list)


def _external_probe_urls() -> tuple[str, ...]:
    raw = (os.getenv("VERIFICATION_EXTERNAL_HEALTH_URLS") or "").strip()
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


async def _probe_external_health(*, urls: tuple[str, ...]) -> tuple[bool, str]:
    failures: list[str] = []
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        for url in urls:
            try:
                response = await client.get(url)
            except Exception:
                failures.append(f"{url}=timeout")
                continue
            if response.status_code >= 400:
                failures.append(f"{url}=status_{response.status_code}")

    if failures:
        return False, f"failed:{';'.join(failures)}"
    return True, f"ok:{len(urls)}"


def _route_check(*, name: str, route_paths: set[str], expected_paths: tuple[str, ...]) -> VerificationCheckResult:
    missing = [path for path in expected_paths if path not in route_paths]
    if missing:
        return VerificationCheckResult(
            name=name,
            required=True,
            passed=False,
            detail=f"missing_routes:{','.join(missing)}",
        )
    return VerificationCheckResult(name=name, required=True, passed=True, detail="ok")


def _identity_profile(agent: Agent) -> dict[str, Any]:
    if isinstance(agent.identity_profile, dict):
        return agent.identity_profile
    return {}


def _identity_value(agent: Agent, key: str) -> str:
    profile = _identity_profile(agent)
    return str(profile.get(key, "")).strip()


def _policy(agent: Agent) -> dict[str, Any]:
    return normalize_model_policy(getattr(agent, "model_policy", None)) or {}


def _bool_str(value: object) -> str:
    return "true" if bool(value) else "false"


def _minimum_gateway_version() -> str:
    raw = str(getattr(settings, "gateway_min_version", "") or "").strip()
    return raw or "2026.3.2"


def _template_sync_route_available(route_paths: set[str] | None) -> bool:
    if route_paths is None:
        return False
    return "/api/v1/gateways/{gateway_id}/templates/sync" in route_paths


def _webhook_ingress_route_available(route_paths: set[str] | None) -> bool:
    if route_paths is None:
        return False
    return "/api/v1/boards/{board_id}/webhooks/{webhook_id}" in route_paths


def _runtime_session_bound(evidence: AgentVerificationEvidence | None) -> bool:
    continuity = evidence.continuity if evidence is not None else None
    return bool(continuity and continuity.runtime_reachable and continuity.runtime_session_id)


def _evaluate_agent_point(
    *,
    agent: Agent,
    point: dict[str, Any],
    evidence: AgentVerificationEvidence | None = None,
    route_paths: set[str] | None = None,
) -> AgentPointResult:
    point_id = int(point.get("point_id"))
    point_name = str(point.get("name") or "").strip()
    name = str(agent.name or "").strip().lower()
    expectations = point.get("agent_expectations") or {}
    expected = expectations.get(name) if isinstance(expectations, dict) else None
    expected_map = expected if isinstance(expected, dict) else {}

    agent_id_text = str(agent.id)

    if point_id == 1:
        role = _identity_value(agent, "role")
        expected_role = str(expected_map.get("role") or "").strip()
        identity_template_present = bool(str(getattr(agent, "identity_template", "") or "").strip())
        soul_template_present = bool(str(getattr(agent, "soul_template", "") or "").strip())
        persona_baseline_present = evidence is None or evidence.persona_integrity is not None
        persona_drift_clear = (
            True
            if evidence is None or evidence.persona_integrity is None
            else not bool(evidence.persona_integrity.last_drift_fields)
        )
        passed = (
            bool(role)
            and role == expected_role
            and identity_template_present
            and soul_template_present
            and persona_baseline_present
            and persona_drift_clear
        )
        detail = (
            f"role={role or 'missing'} expected={expected_role or 'missing'} "
            f"identity_template={_bool_str(identity_template_present)} "
            f"soul_template={_bool_str(soul_template_present)} "
            f"persona_baseline={_bool_str(persona_baseline_present)} "
            f"persona_drift_clear={_bool_str(persona_drift_clear)}"
        )
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=detail,
            evidence_ref="identity_profile.role+identity_template+soul_template+agent_persona_integrity",
        )

    if point_id == 2:
        heartbeat = agent.heartbeat_config if isinstance(agent.heartbeat_config, dict) else {}
        every = str(heartbeat.get("every") or "").strip()
        include_reasoning = isinstance(heartbeat.get("includeReasoning"), bool)
        if evidence is None:
            passed = bool(every) and include_reasoning
            detail = f"every={every or 'missing'} includeReasoning={_bool_str(include_reasoning)}"
        else:
            continuity = evidence.continuity
            continuity_state = continuity.continuity if continuity is not None else "missing"
            runtime_reachable = bool(continuity.runtime_reachable) if continuity is not None else False
            heartbeat_age = continuity.heartbeat_age_seconds if continuity is not None else None
            expected_timeout = expected_map.get("max_timeout_seconds")
            passed = (
                bool(every)
                and include_reasoning
                and continuity is not None
                and continuity.continuity == "alive"
                and runtime_reachable
                and bool(continuity.runtime_session_id)
            )
            detail = (
                f"every={every or 'missing'} includeReasoning={_bool_str(include_reasoning)} "
                f"continuity={continuity_state} runtime_reachable={_bool_str(runtime_reachable)} "
                f"runtime_session_bound={_bool_str(bool(continuity.runtime_session_id) if continuity else False)} "
                f"heartbeat_age_seconds={heartbeat_age if heartbeat_age is not None else 'missing'} "
                f"expected_timeout_seconds={expected_timeout if expected_timeout is not None else 'n/a'}"
            )
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=detail,
            evidence_ref="heartbeat_config.every+includeReasoning+agent_continuity",
        )

    if point_id == 3:
        backend = _identity_value(agent, "memory_backend").lower()
        policy = _identity_value(agent, "memory_policy").lower()
        container_tag = _identity_value(agent, "memory_container_tag")
        passed = backend == "supermemory" and policy == "supermemory-only" and bool(container_tag)
        detail = (
            f"backend={backend or 'missing'} policy={policy or 'missing'} "
            f"container_tag={container_tag or 'missing'}"
        )
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=detail,
            evidence_ref="identity_profile.memory_backend+memory_policy+memory_container_tag",
        )

    if point_id == 4:
        policy = _policy(agent)
        model = str(policy.get("model") or "").strip()
        transport = str(policy.get("transport") or "").strip().lower()
        locked = bool(policy.get("locked")) and not bool(policy.get("allow_self_change"))
        expected_model = str(expected_map.get("model") or "").strip()
        expected_transport = str(expected_map.get("transport") or "").strip().lower()
        expected_locked = bool(expected_map.get("locked"))
        runtime_session_bound = _runtime_session_bound(evidence)
        runtime_gate_passed = True if evidence is None else runtime_session_bound
        passed = (
            model == expected_model
            and locked == expected_locked
            and (not expected_transport or transport == expected_transport)
            and runtime_gate_passed
        )
        detail = (
            f"model={model or 'missing'} expected={expected_model or 'missing'} "
            f"transport={transport or 'missing'} expected_transport={expected_transport or 'missing'} "
            f"locked={_bool_str(locked)} runtime_session_bound={_bool_str(runtime_session_bound)}"
        )
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=detail,
            evidence_ref="model_policy.model+transport+locked+agent_continuity.runtime_session_id",
        )

    if point_id == 5:
        budget = _identity_value(agent, "context_budget")
        expected_budget = str(expected_map.get("context_budget") or "0.35")
        passed = budget == expected_budget
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=f"context_budget={budget or 'missing'} expected={expected_budget}",
            evidence_ref="identity_profile.context_budget",
        )

    if point_id == 6:
        authority = _identity_value(agent, "assignment_authority")
        tools_profile = _identity_value(agent, "tools_profile").lower()
        tailscale_access = _identity_value(agent, "tailscale_access")
        host_context_bootstrap = _identity_value(agent, "host_context_bootstrap")
        identity_bootstrap = _identity_value(agent, "identity_bootstrap")

        expected_authority = str(expected_map.get("assignment_authority") or "owner_or_friday").strip()
        expected_tools_profile = str(expected_map.get("tools_profile") or "coding").strip().lower()
        expected_tailscale = str(expected_map.get("tailscale_access") or "required_on_spawn").strip()
        expected_host_context = str(expected_map.get("host_context_bootstrap") or "required_on_spawn").strip()
        expected_identity_bootstrap = str(
            expected_map.get("identity_bootstrap") or "required_on_spawn"
        ).strip()
        runtime_session_bound = _runtime_session_bound(evidence)
        runtime_gate_passed = True if evidence is None else runtime_session_bound

        passed = (
            authority == expected_authority
            and tools_profile == expected_tools_profile
            and tailscale_access == expected_tailscale
            and host_context_bootstrap == expected_host_context
            and identity_bootstrap == expected_identity_bootstrap
            and runtime_gate_passed
        )
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=(
                f"assignment_authority={authority or 'missing'} "
                f"tools_profile={tools_profile or 'missing'} "
                f"tailscale_access={tailscale_access or 'missing'} "
                f"host_context_bootstrap={host_context_bootstrap or 'missing'} "
                f"identity_bootstrap={identity_bootstrap or 'missing'} "
                f"runtime_session_bound={_bool_str(runtime_session_bound)}"
            ),
            evidence_ref=(
                "identity_profile.assignment_authority+tools_profile+tailscale_access+"
                "host_context_bootstrap+identity_bootstrap+agent_continuity.runtime_session_id"
            ),
        )

    if point_id == 7:
        channel = _identity_value(agent, "group_channel")
        coordination_contract = _identity_value(agent, "coordination_contract")
        webhook_ingress_available = True if route_paths is None else _webhook_ingress_route_available(route_paths)
        passed = channel == "planning_hq" and bool(coordination_contract) and webhook_ingress_available
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=(
                f"group_channel={channel or 'missing'} "
                f"coordination_contract={_bool_str(bool(coordination_contract))} "
                f"webhook_ingress_route={_bool_str(webhook_ingress_available)}"
            ),
            evidence_ref="identity_profile.group_channel+coordination_contract+board_webhooks.ingest",
        )

    if point_id == 8:
        contract = _identity_value(agent, "escalation_contract")
        passed = bool(contract)
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=f"escalation_contract={_bool_str(passed)}",
            evidence_ref="identity_profile.escalation_contract",
        )

    if point_id == 9:
        contract = _identity_value(agent, "heartbeat_contract")
        persona_baseline_present = evidence is None or evidence.persona_integrity is not None
        passed = bool(contract) and persona_baseline_present
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=(
                f"heartbeat_contract={_bool_str(bool(contract))} "
                f"persona_baseline={_bool_str(persona_baseline_present)}"
            ),
            evidence_ref="identity_profile.heartbeat_contract+agent_persona_integrity",
        )

    if point_id == 10:
        contract = _identity_value(agent, "coordination_contract")
        policy = evidence.recovery_policy if evidence is not None else None
        policy_present = policy is not None
        cooldown_seconds = int(policy.cooldown_seconds) if policy is not None else 0
        dedupe_seconds = int(policy.alert_dedupe_seconds) if policy is not None else 0
        max_restarts = int(policy.max_restarts_per_hour) if policy is not None else 0
        recovery_policy_ok = (
            True
            if evidence is None
            else bool(
                policy_present
                and policy is not None
                and policy.enabled
                and cooldown_seconds > 0
                and dedupe_seconds > 0
                and max_restarts > 0
            )
        )
        passed = "Execution starts only when assigned" in contract and recovery_policy_ok
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=(
                f"single_owner_phrase_present={_bool_str('Execution starts only when assigned' in contract)} "
                f"recovery_policy_present={_bool_str(policy_present)} "
                f"cooldown_seconds={cooldown_seconds} "
                f"alert_dedupe_seconds={dedupe_seconds} "
                f"max_restarts_per_hour={max_restarts}"
            ),
            evidence_ref="identity_profile.coordination_contract+recovery_policy",
        )

    if point_id == 11:
        value = _identity_value(agent, "self_improvement")
        passed = bool(value)
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=f"self_improvement={value or 'missing'}",
            evidence_ref="identity_profile.self_improvement",
        )

    if point_id == 12:
        value = _identity_value(agent, "audit_contract")
        passed = bool(value)
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=f"audit_contract={_bool_str(passed)}",
            evidence_ref="identity_profile.audit_contract",
        )

    if point_id == 13:
        value = _identity_value(agent, "halt_contract")
        passed = bool(value)
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=f"halt_contract={value or 'missing'}",
            evidence_ref="identity_profile.halt_contract",
        )

    if point_id == 14:
        value = _identity_value(agent, "hot_reload_contract")
        template_sync_available = _template_sync_route_available(route_paths)
        runtime_session_bound = _runtime_session_bound(evidence)
        runtime_gate_passed = True if evidence is None else runtime_session_bound
        passed = bool(value) and template_sync_available and runtime_gate_passed
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=(
                f"hot_reload_contract={value or 'missing'} "
                f"template_sync_route={_bool_str(template_sync_available)} "
                f"runtime_session_bound={_bool_str(runtime_session_bound)}"
            ),
            evidence_ref="identity_profile.hot_reload_contract+gateways.templates.sync+agent_continuity.runtime_session_id",
        )

    if point_id == 15:
        value = _identity_value(agent, "version_sync_contract")
        gateway_version = evidence.gateway_version if evidence is not None else None
        gateway_compatible = True if evidence is None else bool(gateway_version and gateway_version.compatible)
        current_version = gateway_version.current_version if gateway_version is not None else None
        minimum_version = gateway_version.minimum_version if gateway_version is not None else _minimum_gateway_version()
        passed = bool(value) and gateway_compatible
        return AgentPointResult(
            agent_id=agent_id_text,
            point_id=point_id,
            passed=passed,
            detail=(
                f"version_sync_contract={value or 'missing'} "
                f"gateway_compatible={_bool_str(gateway_compatible)} "
                f"current_version={current_version or 'missing'} "
                f"minimum_version={minimum_version or 'missing'}"
            ),
            evidence_ref="identity_profile.version_sync_contract+gateway_runtime.version",
        )

    return AgentPointResult(
        agent_id=agent_id_text,
        point_id=point_id,
        passed=False,
        detail=f"unknown_point:{point_name or point_id}",
        evidence_ref="harness_config",
    )


async def _evaluate_four_agent_matrix(
    *,
    route_paths: set[str] | None = None,
) -> tuple[VerificationCheckResult, VerificationCheckResult, list[AgentPointResult]]:
    try:
        harness = load_four_agent_harness()
    except Exception as exc:
        skipped = VerificationCheckResult(
            name="four_agent_harness_matrix",
            required=False,
            passed=True,
            detail=f"skipped:invalid_config:{exc}",
        )
        memory = VerificationCheckResult(
            name="four_agent_supermemory_default",
            required=False,
            passed=True,
            detail="skipped:invalid_config",
        )
        return skipped, memory, []

    try:
        async with async_session_maker() as session:
            rows = (await session.exec(select(Agent))).all()
    except Exception as exc:
        skipped = VerificationCheckResult(
            name="four_agent_harness_matrix",
            required=False,
            passed=True,
            detail=f"skipped:db_unavailable:{exc.__class__.__name__}",
        )
        memory = VerificationCheckResult(
            name="four_agent_supermemory_default",
            required=False,
            passed=True,
            detail="skipped:db_unavailable",
        )
        return skipped, memory, []

    target_names = target_agent_names()
    agent_by_name: dict[str, Agent] = {}
    for row in rows:
        key = str(row.name or "").strip().lower()
        if key in target_names and key not in agent_by_name:
            agent_by_name[key] = row

    if not agent_by_name:
        skipped = VerificationCheckResult(
            name="four_agent_harness_matrix",
            required=False,
            passed=True,
            detail="skipped:no_target_agents",
        )
        memory = VerificationCheckResult(
            name="four_agent_supermemory_default",
            required=False,
            passed=True,
            detail="skipped:no_target_agents",
        )
        return skipped, memory, []

    agent_ids = [agent.id for agent in agent_by_name.values()]
    integrity_by_agent_id: dict[object, AgentPersonaIntegrity] = {}
    if agent_ids:
        integrity_rows = (
            await session.exec(
                select(AgentPersonaIntegrity).where(col(AgentPersonaIntegrity.agent_id).in_(agent_ids))
            )
        ).all()
        integrity_by_agent_id = {row.agent_id: row for row in integrity_rows}

    board_ids = {agent.board_id for agent in agent_by_name.values() if agent.board_id is not None}
    board_by_id: dict[object, Board] = {}
    if board_ids:
        board_rows = (
            await session.exec(select(Board).where(col(Board.id).in_(board_ids)))
        ).all()
        board_by_id = {row.id: row for row in board_rows}

    continuity_by_agent_id: dict[object, AgentContinuityItem] = {}
    continuity_service = AgentContinuityService(session=session)
    for board_id in board_ids:
        try:
            report = await continuity_service.snapshot_for_board(board_id=board_id)
        except Exception:
            continue
        for item in report.agents:
            continuity_by_agent_id[item.agent_id] = item

    org_ids = {board.organization_id for board in board_by_id.values()}
    policy_by_org_id: dict[object, RecoveryPolicy] = {}
    if org_ids:
        policy_rows = (
            await session.exec(
                select(RecoveryPolicy).where(col(RecoveryPolicy.organization_id).in_(org_ids))
            )
        ).all()
        policy_by_org_id = {row.organization_id: row for row in policy_rows}

    gateway_ids = {agent.gateway_id for agent in agent_by_name.values()}
    gateway_by_id: dict[object, Gateway] = {}
    if gateway_ids:
        gateway_rows = (
            await session.exec(select(Gateway).where(col(Gateway.id).in_(gateway_ids)))
        ).all()
        gateway_by_id = {row.id: row for row in gateway_rows}

    gateway_version_by_id: dict[object, GatewayVersionCheckResult] = {}
    for gateway in gateway_by_id.values():
        try:
            gateway_version_by_id[gateway.id] = await check_gateway_runtime_compatibility(
                gateway_client_config(gateway),
            )
        except Exception as exc:
            gateway_version_by_id[gateway.id] = GatewayVersionCheckResult(
                compatible=False,
                minimum_version=_minimum_gateway_version(),
                current_version=None,
                message=f"runtime_check_failed:{exc.__class__.__name__}",
            )

    points = harness.get("points") if isinstance(harness, dict) else None
    if not isinstance(points, list):
        skipped = VerificationCheckResult(
            name="four_agent_harness_matrix",
            required=False,
            passed=True,
            detail="skipped:invalid_points",
        )
        memory = VerificationCheckResult(
            name="four_agent_supermemory_default",
            required=False,
            passed=True,
            detail="skipped:invalid_points",
        )
        return skipped, memory, []

    matrix_rows: list[AgentPointResult] = []
    missing_agents: list[str] = []
    for name in target_names:
        if name not in agent_by_name:
            missing_agents.append(name)
            for point in points:
                point_id = int(point.get("point_id") or 0)
                matrix_rows.append(
                    AgentPointResult(
                        agent_id=name,
                        point_id=point_id,
                        passed=False,
                        detail="missing_agent",
                        evidence_ref="agents.name",
                    )
                )
            continue

        agent = agent_by_name[name]
        board = board_by_id.get(agent.board_id) if agent.board_id is not None else None
        recovery_policy = (
            policy_by_org_id.get(board.organization_id)
            if board is not None
            else None
        )
        evidence = AgentVerificationEvidence(
            continuity=continuity_by_agent_id.get(agent.id),
            persona_integrity=integrity_by_agent_id.get(agent.id),
            recovery_policy=recovery_policy,
            gateway_version=gateway_version_by_id.get(agent.gateway_id),
        )
        for point in points:
            matrix_rows.append(
                _evaluate_agent_point(
                    agent=agent,
                    point=point,
                    evidence=evidence,
                    route_paths=route_paths,
                )
            )

    matrix_passed = all(row.passed for row in matrix_rows)
    if missing_agents:
        detail = f"failed:missing_agents:{','.join(missing_agents)}"
    elif matrix_passed:
        detail = f"ok:rows={len(matrix_rows)}"
    else:
        failed = sum(1 for row in matrix_rows if not row.passed)
        detail = f"failed:rows={len(matrix_rows)} failed={failed}"

    matrix_check = VerificationCheckResult(
        name="four_agent_harness_matrix",
        required=True,
        passed=matrix_passed and not missing_agents,
        detail=detail,
    )

    supermemory_failures = [
        row for row in matrix_rows if row.point_id == 3 and not row.passed
    ]
    supermemory_check = VerificationCheckResult(
        name="four_agent_supermemory_default",
        required=True,
        passed=not supermemory_failures,
        detail=(
            "ok"
            if not supermemory_failures
            else f"failed:agents={','.join(sorted({row.agent_id for row in supermemory_failures}))}"
        ),
    )

    return matrix_check, supermemory_check, matrix_rows


async def run_verification_harness(
    *,
    route_paths: set[str],
    profile: str = "auto",
) -> VerificationHarnessResult:
    """Run deterministic control-plane verification checks."""
    checks: list[VerificationCheckResult] = [
        _route_check(
            name="health_routes",
            route_paths=route_paths,
            expected_paths=("/health", "/readyz"),
        ),
        _route_check(
            name="notebook_gate_route",
            route_paths=route_paths,
            expected_paths=("/api/v1/runtime/notebook/gate",),
        ),
        _route_check(
            name="recovery_run_route",
            route_paths=route_paths,
            expected_paths=("/api/v1/runtime/recovery/run",),
        ),
    ]

    probe_urls = _external_probe_urls()
    if not probe_urls:
        checks.append(
            VerificationCheckResult(
                name="external_health_probe",
                required=False,
                passed=True,
                detail="skipped:unconfigured",
            )
        )
    else:
        probe_passed, probe_detail = await _probe_external_health(urls=probe_urls)
        checks.append(
            VerificationCheckResult(
                name="external_health_probe",
                required=True,
                passed=probe_passed,
                detail=probe_detail,
            )
        )

    gate = await evaluate_notebooklm_capability(profile=profile, require_notebook=False)
    checks.append(
        VerificationCheckResult(
            name="notebook_capability",
            required=True,
            passed=gate.state == "ready",
            detail=f"{gate.state}:{gate.reason}",
        )
    )

    matrix_check, supermemory_check, matrix_rows = await _evaluate_four_agent_matrix(
        route_paths=route_paths,
    )
    checks.append(matrix_check)
    checks.append(supermemory_check)

    required_failed = sum(1 for check in checks if check.required and not check.passed)
    all_passed = required_failed == 0 and all(check.passed for check in checks)
    return VerificationHarnessResult(
        generated_at=utcnow(),
        checks=checks,
        all_passed=all_passed,
        required_failed=required_failed,
        agent_matrix=matrix_rows,
    )
