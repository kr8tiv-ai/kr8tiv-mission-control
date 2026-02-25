# Auto-Improve Control Plane

This document defines how Mission Control manages autonomous OpenClaw harnesses at scale without losing speed, personality, or operational quality.

## Charter

- Build a self-improving fleet, not isolated one-off agents.
- Optimize for measurable outcomes and fast iteration.
- Keep controls focused on reliability, privacy, and quality.
- Avoid process overhead that does not improve production behavior.

## System Boundary

| Concern | OpenClaw Harness | Mission Control |
|---|---|---|
| Agent runtime and tool execution | Owns | Observes |
| User interaction and local personalization | Owns | Configures policy envelope |
| Prompt/context generation ideas | Suggests | Owns approval and deployment |
| Evaluation and scoring | Optional local checks | Owns canonical eval stack |
| Promotion and rollback | Consumes commands | Owns decisions |
| Multi-tenant policy and RBAC | Enforces received rules | Owns source of truth |

## Scope and Inheritance

Prompt/context packs resolve in this order:

`global -> domain -> tenant -> user`

Rules:

- Child scopes can extend behavior.
- Child scopes cannot break global hard constraints.
- Tenant data does not cross tenant boundaries by default.
- User data does not cross user boundaries by default.

## Pack Model

Each deployable domain pack should define:

- Prompt/context bundle
- Tool permission profile
- Eval rubric and expected output contracts
- KPI targets
- Promotion thresholds
- Rollback defaults

Example packs:

- `hr-ops-pack`
- `legal-intake-pack`
- `infra-sre-pack`
- `engineering-delivery-pack`
- `personal-exec-assistant-pack`

## Required Data Contracts

### `prompt_pack`

- `id`
- `scope_type` (`global|domain|tenant|user`)
- `scope_id`
- `version`
- `status` (`champion|challenger|archived`)
- `created_by`
- `created_at`

### `run_telemetry`

- `run_id`
- `tenant_id`
- `user_id`
- `agent_id`
- `pack_id`
- `pack_version`
- `task_type`
- `latency_ms`
- `cost_usd`
- `success_bool`
- `error_code`
- `created_at`

### `eval_result`

- `eval_id`
- `run_id`
- `deterministic_score`
- `llm_judge_score`
- `safety_regression_bool`
- `format_regression_bool`
- `comments`
- `created_at`

### `promotion_decision`

- `decision_id`
- `scope_type`
- `scope_id`
- `champion_pack_version`
- `challenger_pack_version`
- `decision` (`promote|reject|rollback`)
- `reason`
- `decided_by`
- `created_at`

## Promotion Pipeline

1. Ingest run telemetry from harnesses.
2. Build challenger candidates (nightly or weekly cadence).
3. Execute deterministic evals.
4. Execute LLM-judge evals for subjective quality.
5. Compare challenger vs champion by threshold.
6. Block if any hard regression is detected.
7. Promote with canary rollout, then full rollout.
8. Roll back instantly on KPI or reliability regression.

## Tier Model

### Personal Tier

- Local-first experience
- Lower-cost optimization cadence
- Strict user-scoped memory and adaptation

### Team Tier

- Shared domain packs
- Manager approvals for medium-risk actions
- Cross-user metrics at team scope

### Enterprise Tier

- SSO/RBAC integration
- Tenant-scoped policy packs
- Approval workflows by role
- Audit history and rollback requirements

## Iterative Delivery Plan

### Stage 0: Baseline and schemas

- Finalize contract tables and event payloads.
- Attach pack version IDs to all harness runs.
- Track baseline KPIs.

### Stage 1: Registry and rollback

- Ship pack registry API.
- Ship runtime pack resolution.
- Ship one-click rollback path.

### Stage 2: Evaluation gate

- Add deterministic evaluator worker.
- Add LLM-judge evaluator worker.
- Require approval for promotion.

### Stage 3: Controlled self-improvement

- Add challenger generation worker.
- Add budget caps and candidate caps.
- Add canary rollout for promotions.

### Stage 4: Tiered scale

- Add personal/team/enterprise policy presets.
- Add domain-pack marketplace UX.
- Add tenant and user isolation checks in CI.

## Budget and Risk Guardrails

- `max_optimization_spend_per_day` per tenant
- `max_candidates_per_run`
- `max_prompt_growth_tokens`
- `max_allowed_latency_regression_pct`
- Hard block on safety and format regressions

## Personality and Autonomy

Personality is versioned as part of the pack, not ad hoc per agent.

- Keep voice profiles explicit and testable.
- Measure voice quality separately from task correctness.
- Use autonomy levels (`A0` observe, `A1` low-risk auto, `A2` approval-needed, `A3` explicit approval path).

## Definition of Done for this architecture

- Every production run is traceable to pack version and scope.
- Every promotion is backed by eval evidence.
- Every rollout is reversible quickly.
- Personal and enterprise lanes run on the same control-plane model with different policy presets.
