# Phase 23-25 Control Plane Visibility + Continuity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Continue GSD reliability delivery after phases 20-22 by adding capability visibility, richer continuity telemetry, and a deterministic validation gate that ties rollout proof to GSD run progression.

**Architecture:** Deliver in three slices. Phase 23 adds notebook capability observability to task payloads and UI. Phase 24 adds run-level metric aggregation plus previous-iteration deltas. Phase 25 adds executable rollout verification and stage-gate wiring into GSD runs. Keep all additions backward-compatible and fail-safe.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, Next.js/React, Vitest.

---

### Task 1: Phase 23 Notebook Gate State Model for Task Surfaces

**Files:**
- Modify: `backend/app/models/tasks.py`
- Modify: `backend/app/schemas/tasks.py`
- Create: `backend/migrations/versions/<new_revision>_add_task_notebook_gate_fields.py`
- Test: `backend/tests/test_task_notebook_gate_state.py`

**Step 1: Write failing tests**

Add tests verifying notebook-enabled tasks expose:
- `notebook_gate_state`
- `notebook_gate_reason`
- `notebook_gate_checked_at`

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_task_notebook_gate_state.py -q`
Expected: FAIL (fields missing).

**Step 3: Write minimal implementation**

Add nullable task fields and read schema properties for notebook gate state.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_task_notebook_gate_state.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/tasks.py backend/app/schemas/tasks.py backend/migrations/versions/*.py backend/tests/test_task_notebook_gate_state.py
git commit -m "feat: add task-level notebook gate state fields"
```

### Task 2: Phase 23 Persist Gate Results in Notebook Task Paths

**Files:**
- Modify: `backend/app/services/task_mode_execution.py`
- Modify: `backend/app/api/tasks.py`
- Modify: `backend/tests/test_task_mode_notebook_capability_gate.py`
- Modify: `backend/tests/test_tasks_api_rows.py`

**Step 1: Write failing tests**

Cover that blocked notebook operations persist gate state/reason/timestamp on task rows and return deterministic payloads.

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_task_mode_notebook_capability_gate.py tests/test_tasks_api_rows.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Persist gate result fields whenever capability check runs (ready + blocked), and include in task API response.

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_task_mode_notebook_capability_gate.py tests/test_tasks_api_rows.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/task_mode_execution.py backend/app/api/tasks.py backend/tests/test_task_mode_notebook_capability_gate.py backend/tests/test_tasks_api_rows.py
git commit -m "feat: persist notebook gate outcomes in task execution paths"
```

### Task 3: Phase 23 Board-Level Notebook Gate Summary Endpoint

**Files:**
- Modify: `backend/app/api/notebook_ops.py`
- Modify: `backend/app/schemas/notebook_ops.py`
- Test: `backend/tests/test_notebook_ops_api.py`

**Step 1: Write failing tests**

Add tests for:
- `GET /api/v1/runtime/notebook/gate-summary?board_id=<uuid>`
- deterministic counts by gate state
- auth/org scoping

**Step 2: Run tests to verify fail**

Run: `cd backend && uv run pytest tests/test_notebook_ops_api.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement summary response from task-level gate fields for notebook-enabled task modes.

**Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/test_notebook_ops_api.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/notebook_ops.py backend/app/schemas/notebook_ops.py backend/tests/test_notebook_ops_api.py
git commit -m "feat: add board notebook gate summary endpoint"
```

### Task 4: Phase 23 Frontend Gate Visibility in Task Board

**Files:**
- Modify: `frontend/src/components/organisms/TaskBoard.tsx`
- Modify: `frontend/src/components/molecules/TaskCard.tsx`
- Test: `frontend/src/components/organisms/TaskBoard.test.tsx`

**Step 1: Write failing tests**

Add tests that notebook-enabled tasks show gate badges and blocked tasks can be filtered.

**Step 2: Run tests to verify fail**

Run: `cd frontend && npm test -- TaskBoard.test.tsx --runInBand`
Expected: FAIL.

**Step 3: Write minimal implementation**

Render gate state badges and remediation hints from API payload; add filter chips for blocked/retryable notebook tasks.

**Step 4: Run tests to verify pass**

Run: `cd frontend && npm test -- TaskBoard.test.tsx --runInBand`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/organisms/TaskBoard.tsx frontend/src/components/molecules/TaskCard.tsx frontend/src/components/organisms/TaskBoard.test.tsx
git commit -m "feat: expose notebook gate health in task board ui"
```

### Task 5: Phase 24 GSD Metrics Aggregation Service

**Files:**
- Create: `backend/app/services/runtime/gsd_metrics_aggregator.py`
- Modify: `backend/app/services/runtime/gsd_metrics_sync.py`
- Test: `backend/tests/test_gsd_metrics_aggregator.py`

**Step 1: Write failing tests**

Cover aggregation for:
- incident counters
- retry count
- latency p95
- gate block rate

**Step 2: Run tests to verify fail**

Run: `cd backend && uv run pytest tests/test_gsd_metrics_aggregator.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Aggregate and normalize metrics from recovery + task mode + deterministic eval artifacts into snapshot payload.

**Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/test_gsd_metrics_aggregator.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/runtime/gsd_metrics_aggregator.py backend/app/services/runtime/gsd_metrics_sync.py backend/tests/test_gsd_metrics_aggregator.py
git commit -m "feat: add continuity metrics aggregation for gsd runs"
```

### Task 6: Phase 24 GSD Run Summary + Delta Endpoint

**Files:**
- Modify: `backend/app/api/gsd_runs.py`
- Modify: `backend/app/schemas/gsd_runs.py`
- Test: `backend/tests/test_gsd_runs_api.py`

**Step 1: Write failing tests**

Add tests for:
- `GET /api/v1/gsd-runs/{run_id}/summary`
- includes previous iteration baseline + delta payload

**Step 2: Run tests to verify fail**

Run: `cd backend && uv run pytest tests/test_gsd_runs_api.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Add summary endpoint and deterministic delta calculations for numeric metrics.

**Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/test_gsd_runs_api.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/gsd_runs.py backend/app/schemas/gsd_runs.py backend/tests/test_gsd_runs_api.py
git commit -m "feat: add gsd run summary endpoint with phase-over-phase deltas"
```

### Task 7: Phase 25 Runtime Verification Harness + GSD Gate Wiring

**Files:**
- Create: `backend/app/services/runtime/verification_harness.py`
- Create: `backend/app/api/verification_ops.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_verification_harness_api.py`

**Step 1: Write failing tests**

Cover:
- verification execute endpoint returns pass/fail matrix
- optional `gsd_run_id` links evidence and updates run status
- blocked transition when required checks fail

**Step 2: Run tests to verify fail**

Run: `cd backend && uv run pytest tests/test_verification_harness_api.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement harness runner with pluggable checks (health, notebook gate, recovery probe, OpenAPI route presence) and link result into GSD run updates.

**Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/test_verification_harness_api.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/runtime/verification_harness.py backend/app/api/verification_ops.py backend/app/main.py backend/tests/test_verification_harness_api.py
git commit -m "feat: add runtime verification harness and gsd gate integration"
```

### Task 8: Verification Sweep + Docs + Rollout Evidence

**Files:**
- Modify: `docs/operations/2026-02-25-live-recovery-rollout.md`
- Modify: `docs/mission-control-task-modes.md`
- Modify: `docs/openclaw_15_point_harness.md`

**Step 1: Run backend regression**

Run:
`cd backend && $env:UV_PROJECT_ENVIRONMENT='.venv-test'; uv run pytest tests/test_notebooklm_capability_gate.py tests/test_task_mode_notebook_capability_gate.py tests/test_task_mode_supermemory_callout.py tests/test_task_mode_schema.py tests/test_tasks_api_rows.py tests/test_notebook_ops_api.py tests/test_gsd_runs_api.py tests/test_recovery_ops_api.py tests/test_gsd_metrics_aggregator.py tests/test_verification_harness_api.py -q`

Expected: PASS.

**Step 2: Run frontend regression/build**

Run:
`cd frontend && npm test -- TaskBoard.test.tsx --runInBand`
`cd frontend && npm run build`

Expected: PASS.

**Step 3: Document rollout evidence**

Append per-phase evidence:
- immutable image tags
- Hostinger action IDs
- health/ready checks
- notebook gate summary sample
- GSD run summary delta sample
- verification harness result payload

**Step 4: Commit**

```bash
git add docs/operations/2026-02-25-live-recovery-rollout.md docs/mission-control-task-modes.md docs/openclaw_15_point_harness.md
git commit -m "docs: add phase23-25 rollout verification and gsd continuity evidence"
```
