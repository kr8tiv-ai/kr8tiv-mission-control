# Phase 20-22 Heartbeat + Capability Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate heartbeat-driven instability, add deterministic NotebookLM capability gating, and extend GSD telemetry so reliability gains are measurable phase-over-phase.

**Architecture:** Implement in three phases: (20) heartbeat/channel stability controls, (21) NotebookLM preflight/capability gate, (22) telemetry model + API expansion for recovery/continuity metrics. Keep behavior backward-compatible where possible and fail fast on unsupported runtime states.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, OpenClaw gateway config patching, NotebookLM CLI adapter.

---

### Task 1: Phase 20 Heartbeat Contract (No Short-Circuit Idle Acks)

**Files:**
- Modify: `backend/templates/BOARD_HEARTBEAT.md.j2`
- Create: `backend/tests/test_heartbeat_template_contract.py`

**Step 1: Write failing test**

Add test to assert heartbeat template requires:
1. one Mission Control probe before `HEARTBEAT_OK`
2. explicit timeout-safe fallback wording
3. no "instant HEARTBEAT_OK without checks" phrasing.

**Step 2: Run test to verify fail**

Run:
`cd backend && uv run pytest tests/test_heartbeat_template_contract.py -q`

Expected: FAIL (contract text missing).

**Step 3: Implement minimal template change**

Update heartbeat template text to require:
1. lightweight API/task probe first
2. return `HEARTBEAT_OK` only after probe yields no actionable work.

**Step 4: Re-run test**

Run:
`cd backend && uv run pytest tests/test_heartbeat_template_contract.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/templates/BOARD_HEARTBEAT.md.j2 backend/tests/test_heartbeat_template_contract.py
git commit -m "feat: enforce heartbeat probe-before-idle contract"
```

### Task 2: Phase 20 Channel/Poller Stability Guards

**Files:**
- Modify: `backend/app/services/openclaw/provisioning.py`
- Modify: `backend/tests/test_agent_provisioning_utils.py`
- Modify: `backend/docs/openclaw_15_point_harness.md`

**Step 1: Write failing tests**

Add/extend tests asserting:
1. `channels.whatsapp.enabled` is never patched (account-level disable only)
2. Telegram `configWrites` locks always set when patching heartbeats
3. fallback candidate patch succeeds on invalid config shapes.

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_agent_provisioning_utils.py -k "patch_agent_heartbeats" -q`

Expected: FAIL before implementation updates.

**Step 3: Implement guard behavior**

Ensure channel patch emits:
1. `channels.telegram.configWrites=false`
2. `channels.telegram.accounts.default.configWrites=false`
3. `channels.whatsapp.accounts.default.enabled=false` only when WhatsApp ingress is disabled.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_agent_provisioning_utils.py -k "patch_agent_heartbeats" -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/openclaw/provisioning.py backend/tests/test_agent_provisioning_utils.py backend/docs/openclaw_15_point_harness.md
git commit -m "fix: harden channel patch schema compatibility and poller stability guards"
```

### Task 3: Phase 21 NotebookLM Capability Gate Service

**Files:**
- Create: `backend/app/services/notebooklm_capability_gate.py`
- Modify: `backend/app/services/notebooklm_adapter.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_notebooklm_capability_gate.py`

**Step 1: Write failing tests**

Cover:
1. gate success when runner/profile checks pass
2. gate retryable classification for timeouts/auth refresh scenarios
3. gate misconfig classification for missing profile/notebook id
4. gate hard-fail classification for explicit forbidden/account lock signals.

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_notebooklm_capability_gate.py -q`

Expected: FAIL (service missing).

**Step 3: Implement minimal gate**

Add a typed gate result:
1. `state` (`ready`, `retryable`, `misconfig`, `hard_fail`)
2. `reason`
3. `operator_message`

Use adapter-level probes with bounded timeout.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_notebooklm_capability_gate.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/notebooklm_capability_gate.py backend/app/services/notebooklm_adapter.py backend/app/core/config.py backend/tests/test_notebooklm_capability_gate.py
git commit -m "feat: add notebooklm capability gate service with deterministic failure classes"
```

### Task 4: Phase 21 Gate Integration in Task Execution Paths

**Files:**
- Modify: `backend/app/services/task_mode_execution.py`
- Modify: `backend/app/api/tasks.py`
- Create: `backend/tests/test_task_mode_notebook_capability_gate.py`
- Modify: `backend/tests/test_tasks_api_rows.py`

**Step 1: Write failing tests**

Cover:
1. notebook mode blocked when gate state is `misconfig` or `hard_fail`
2. notebook mode retries/returns 502 path on `retryable`
3. blocked states write explicit task comments and no silent failure.

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_task_mode_notebook_capability_gate.py tests/test_tasks_api_rows.py -q`

Expected: FAIL before integration.

**Step 3: Implement integration**

Before create/query/add operations:
1. run capability gate
2. map gate state to deterministic API/task behavior
3. persist `[NotebookLM Gate]` task comment with reason on block.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_task_mode_notebook_capability_gate.py tests/test_tasks_api_rows.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/task_mode_execution.py backend/app/api/tasks.py backend/tests/test_task_mode_notebook_capability_gate.py backend/tests/test_tasks_api_rows.py
git commit -m "feat: enforce notebook capability gate across task execution and task notebook query api"
```

### Task 5: Phase 21 Capability Gate Status Endpoint

**Files:**
- Create: `backend/app/api/notebook_ops.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_notebook_ops_api.py`

**Step 1: Write failing API tests**

Add tests for:
1. `GET /api/v1/runtime/notebook/gate` returns current gate status payload
2. endpoint includes state/reason/timestamp
3. org scoping/auth behavior is enforced.

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_notebook_ops_api.py -q`

Expected: FAIL (route missing).

**Step 3: Implement endpoint**

Expose last computed gate status for operational visibility and runbook automation.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_notebook_ops_api.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/notebook_ops.py backend/app/main.py backend/tests/test_notebook_ops_api.py
git commit -m "feat: add runtime notebook capability gate status api"
```

### Task 6: Phase 22 GSD Run Metrics Model Expansion

**Files:**
- Modify: `backend/app/models/gsd_runs.py`
- Modify: `backend/app/schemas/gsd_runs.py`
- Modify: `backend/app/api/gsd_runs.py`
- Create: `backend/migrations/versions/<new_revision>_add_gsd_run_metrics.py`
- Modify: `backend/tests/test_gsd_runs_api.py`

**Step 1: Write failing tests**

Add coverage for new metrics payload fields (JSON object), including validation and readback.

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_gsd_runs_api.py -q`

Expected: FAIL (fields missing).

**Step 3: Implement model/schema/api**

Add a structured metrics field with baseline keys:
1. `incidents_total`
2. `incidents_recovered`
3. `incidents_failed`
4. `incidents_suppressed`
5. `retry_count`
6. `latency_p95_ms`
7. `tool_failure_rate`

Add Alembic migration.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_gsd_runs_api.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/gsd_runs.py backend/app/schemas/gsd_runs.py backend/app/api/gsd_runs.py backend/migrations/versions/*.py backend/tests/test_gsd_runs_api.py
git commit -m "feat: extend gsd runs with recovery and continuity metrics payload"
```

### Task 7: Phase 22 Runtime-to-GSD Metrics Wiring

**Files:**
- Modify: `backend/app/api/recovery_ops.py`
- Modify: `backend/app/services/runtime/recovery_engine.py`
- Create: `backend/app/services/runtime/gsd_metrics_sync.py`
- Create: `backend/tests/test_gsd_recovery_metrics_sync.py`

**Step 1: Write failing tests**

Add tests that verify recovery run outputs can update a target GSD run metrics snapshot.

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_gsd_recovery_metrics_sync.py -q`

Expected: FAIL (sync service missing).

**Step 3: Implement sync service**

Wire recovery summary (`total_incidents`, `recovered`, `failed`, `suppressed`) into selected GSD run metrics payload.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_gsd_recovery_metrics_sync.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/recovery_ops.py backend/app/services/runtime/recovery_engine.py backend/app/services/runtime/gsd_metrics_sync.py backend/tests/test_gsd_recovery_metrics_sync.py
git commit -m "feat: sync runtime recovery outcomes into gsd run metrics"
```

### Task 8: Full Verification + Rollout Evidence

**Files:**
- Modify: `docs/operations/2026-02-25-live-recovery-rollout.md`
- Modify: `docs/openclaw_15_point_harness.md`
- Modify: `docs/mission-control-task-modes.md`

**Step 1: Run focused backend suite**

Run:
`cd backend && uv run pytest tests/test_agent_provisioning_utils.py tests/test_task_mode_supermemory_callout.py tests/test_task_mode_notebook_capability_gate.py tests/test_notebooklm_capability_gate.py tests/test_notebook_ops_api.py tests/test_gsd_runs_api.py tests/test_gsd_recovery_metrics_sync.py -q`

Expected: PASS.

**Step 2: Run frontend validation**

Run:
`cd frontend && npm test -- --runInBand`
`cd frontend && npm run build`

Expected: PASS.

**Step 3: Document live rollout sequence**

Append:
1. immutable image tags
2. Hostinger action IDs
3. health/ready/board checks
4. notebook gate checks
5. GSD metrics snapshot after forced recovery run.

**Step 4: Commit + Push**

```bash
git add docs/operations/2026-02-25-live-recovery-rollout.md docs/openclaw_15_point_harness.md docs/mission-control-task-modes.md
git commit -m "docs: record phase20-22 rollout verification and notebook capability gate evidence"
git push origin <branch>
```
