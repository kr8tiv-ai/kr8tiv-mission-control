# Phase 23-25 Control Plane Visibility + Continuity Design

Date: 2026-02-27
Status: Proposed
Owner: lucid

## 1. Why This Next Sequence

Phases 20-22 are implemented and validated (`28 passed` targeted backend tests), but three control-plane reliability goals are still only partially delivered:

1. NotebookLM capability gate exists, but visibility is still mostly error-path only (limited proactive operator/UI signal).
2. GSD run telemetry supports `metrics_snapshot`, but runtime metrics are still sparse (mostly recovery counters).
3. Rollout verification exists in docs/runbooks, but there is no deterministic stage gate tying validation evidence directly to GSD progression.

This design defines the next reliability sequence:

- **Phase 23:** Notebook capability visibility + blocked-state UX
- **Phase 24:** GSD continuity metrics aggregation + phase-over-phase delta summaries
- **Phase 25:** Rollout harness automation + GSD validation gate

## 2. Current Baseline (Ground Truth)

1. Notebook capability evaluation is implemented (`evaluate_notebooklm_capability`) and wired into task execution/query paths.
2. Runtime Notebook gate endpoint is available (`GET /api/v1/runtime/notebook/gate`).
3. Recovery summaries can sync into `gsd_runs.metrics_snapshot` through `gsd_run_id` in recovery run API.
4. Mission Control task board currently shows GSD stage/status, but no first-class notebook capability health badges or remediation affordances.

## 3. Phase 23 Design: Capability Visibility + Blocked-State UX

### 3.1 Outcomes

1. Operators can see notebook capability health before triggering notebook-mode tasks.
2. Notebook-gated task failures surface structured reason codes, not only free-text comments.
3. Board UI can show actionable remediation for `retryable`, `misconfig`, `hard_fail` states.

### 3.2 Backend Contracts

1. Add a board-scoped gate summary endpoint:
   - `GET /api/v1/runtime/notebook/gate-summary?board_id=<uuid>`
2. Add structured notebook gate metadata in notebook-enabled task read payloads:
   - `notebook_gate_state`
   - `notebook_gate_reason`
   - `notebook_gate_checked_at`
3. Ensure blocked notebook operations emit machine-readable activity payload and stable reason taxonomy.

### 3.3 Frontend Contracts

1. Task board cards display notebook gate badge for notebook-enabled modes.
2. Filter for "Notebook Blocked" and "Notebook Retryable" tasks.
3. Inline remediation copy from backend `operator_message` (no duplicated frontend logic).

## 4. Phase 24 Design: Continuity Metrics + Deltas

### 4.1 Outcomes

1. GSD runs capture continuity KPIs beyond incidents-only counters.
2. Operators can compare current run vs previous iteration quickly.
3. Reliability improvements are measurable per phase and per board.

### 4.2 Metrics Contract (minimum)

1. `incidents_total`
2. `incidents_recovered`
3. `incidents_failed`
4. `incidents_suppressed`
5. `retry_count`
6. `latency_p95_ms`
7. `tool_failure_rate`
8. `gate_block_rate`

### 4.3 API Contracts

1. Add run summary endpoint:
   - `GET /api/v1/gsd-runs/{run_id}/summary`
2. Response includes:
   - current metrics
   - previous iteration metrics (same run_name + board + org)
   - computed deltas
3. Recovery and task-mode execution paths continue to write partial metrics idempotently.

## 5. Phase 25 Design: Validation Harness + Stage Gate

### 5.1 Outcomes

1. Validation is executable, not a manual checklist only.
2. GSD run transition to `hardening/completed` requires verification evidence.
3. Rollout quality gate is reproducible in CI and operator-run scripts.

### 5.2 Runtime Gate

1. Introduce validation gate endpoint:
   - `POST /api/v1/runtime/verification/execute`
2. Validation set includes:
   - health/ready checks
   - Notebook gate check
   - recovery run probe (dry-run path where available)
   - required OpenAPI route presence checks
3. On pass, attach evidence links and metrics to target `gsd_run_id`.

## 6. Guardrails (Non-Negotiable)

1. Existing GSD stage policy remains enforced (`spec -> plan -> execute -> verify -> done` for tasks).
2. Persona precedence remains strict (`SOUL.md > USER.md > IDENTITY.md > AGENTS.md`).
3. Runtime config writes remain disabled unless explicit owner-approved controls allow exceptions.
4. New telemetry and gate endpoints must degrade safely; no task write path may be bricked by observability failures.

## 7. Acceptance Criteria

1. Phase 23:
   - Notebook gate status visible in board APIs and UI with deterministic reason codes.
2. Phase 24:
   - Run summary endpoint returns deltas and baseline continuity metrics; tests cover aggregation and normalization.
3. Phase 25:
   - Verification harness writes evidence + gate result to `gsd_runs`; blocked transitions produce explicit error payloads.
4. Regression:
   - Existing phase20-22 targeted suite remains green.

## 8. Rollout Sequence

1. Implement Phase 23 (backend + UI + tests) and deploy.
2. Implement Phase 24 (metrics aggregation + summaries + tests) and deploy.
3. Implement Phase 25 (verification harness + stage gate + tests) and deploy.
4. Append live verification evidence to rollout operations log after each deployment.
