# Phase 17 Recovery Scheduler + Alert Dedupe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run recovery continuously in worker runtime and suppress duplicate owner alerts while preserving full incident audit history.

**Architecture:** Add a periodic scheduler service that sweeps boards through the existing recovery engine, then routes alerts with dedupe-window suppression keyed by board/agent/status/reason. Extend recovery policy to carry per-organization dedupe seconds and worker settings for loop cadence.

**Tech Stack:** FastAPI, SQLModel, Alembic, asyncio worker loop, pytest.

---

### Task 1: Policy + Schema Controls for Dedupe Window

**Files:**
- Modify: `backend/app/models/recovery_policies.py`
- Modify: `backend/app/schemas/recovery_ops.py`
- Modify: `backend/app/api/recovery_ops.py`
- Create: `backend/migrations/versions/<new_revision>_add_recovery_alert_dedupe_seconds.py`
- Test: `backend/tests/test_recovery_models.py`
- Test: `backend/tests/test_recovery_ops_api.py`

**Step 1: Write failing tests**

Add assertions:

```python
def test_recovery_policy_defaults_enable_autorestart_with_cooldown():
    assert policy.alert_dedupe_seconds == 900
```

```python
async def test_update_recovery_policy_persists_limits():
    ...
    "alert_dedupe_seconds": 600
```

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_recovery_models.py tests/test_recovery_ops_api.py -q`

Expected: FAIL on missing `alert_dedupe_seconds`.

**Step 3: Implement minimal schema/model/API updates**

- Add `alert_dedupe_seconds: int = Field(default=900)` to `RecoveryPolicy`.
- Add field to `RecoveryPolicyRead` + `RecoveryPolicyUpdate`.
- Ensure update/read endpoints persist/return field.
- Add Alembic migration for column with server default.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_recovery_models.py tests/test_recovery_ops_api.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/recovery_policies.py backend/app/schemas/recovery_ops.py backend/app/api/recovery_ops.py backend/migrations/versions backend/tests/test_recovery_models.py backend/tests/test_recovery_ops_api.py
git commit -m "feat: add recovery alert dedupe policy controls"
```

### Task 2: Recovery Scheduler Service + Dedupe Logic

**Files:**
- Create: `backend/app/services/runtime/recovery_scheduler.py`
- Modify: `backend/app/services/runtime/__init__.py`
- Test: `backend/tests/test_recovery_scheduler.py`

**Step 1: Write failing tests**

Add tests:

```python
async def test_scheduler_runs_recovery_for_board_and_routes_alerts():
    ...
```

```python
async def test_scheduler_suppresses_duplicate_alerts_within_dedupe_window():
    ...
```

```python
async def test_scheduler_ignores_suppressed_incident_status_for_alert_delivery():
    ...
```

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_recovery_scheduler.py -q`

Expected: FAIL (service missing).

**Step 3: Implement minimal scheduler**

- Build board sweep service that:
  - loads boards,
  - runs `RecoveryEngine.evaluate_board`,
  - resolves policy,
  - dedupes matching incident alerts inside `alert_dedupe_seconds`,
  - routes non-duplicate alerts via `RecoveryAlertService`.
- Return summary counters for observability.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_recovery_scheduler.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/runtime/recovery_scheduler.py backend/app/services/runtime/__init__.py backend/tests/test_recovery_scheduler.py
git commit -m "feat: add periodic recovery scheduler with alert dedupe"
```

### Task 3: Worker Integration for Periodic Recovery Ticks

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/queue_worker.py`
- Test: `backend/tests/test_queue_worker_recovery_scheduler.py`

**Step 1: Write failing tests**

Add tests:

```python
async def test_run_recovery_scheduler_once_executes_sweep_when_enabled():
    ...
```

```python
async def test_run_recovery_scheduler_once_is_noop_when_disabled():
    ...
```

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_queue_worker_recovery_scheduler.py -q`

Expected: FAIL (integration hooks missing).

**Step 3: Implement minimal integration**

- Add settings:
  - `recovery_loop_enabled: bool = True`
  - `recovery_loop_interval_seconds: int = 180`
- Add scheduler tick runner in worker loop.
- Run tick at interval boundary without blocking queue dispatch forever.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_queue_worker_recovery_scheduler.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/core/config.py backend/app/services/queue_worker.py backend/tests/test_queue_worker_recovery_scheduler.py
git commit -m "feat: run periodic recovery scheduler inside worker loop"
```

### Task 4: Focused Verification + Phase 17 Docs

**Files:**
- Modify: `docs/openclaw_15_point_harness.md`
- Modify: `docs/operations/2026-02-25-live-recovery-rollout.md`

**Step 1: Run focused backend verification**

Run:
`cd backend && uv run pytest tests/test_recovery_models.py tests/test_recovery_engine.py tests/test_recovery_ops_api.py tests/test_recovery_alert_routing.py tests/test_recovery_scheduler.py tests/test_queue_worker_recovery_scheduler.py -q`

Expected: PASS.

**Step 2: Append Phase 17 validation instructions**

- Add recovery loop checks and dedupe-window validation procedure.

**Step 3: Commit**

```bash
git add docs/openclaw_15_point_harness.md docs/operations/2026-02-25-live-recovery-rollout.md
git commit -m "docs: add phase17 recovery scheduler and dedupe validation"
```

### Task 5: Full Suite + Rollout Evidence

**Files:**
- Modify: `docs/operations/2026-02-25-live-recovery-rollout.md`

**Step 1: Full verification**

```bash
cd backend
uv run pytest tests -q
uv run alembic heads
cd ../frontend
npm test
npm run build
```

**Step 2: Roll immutable images + restart containers**

- Publish backend/frontend SHA tags.
- Pin compose project to those tags.
- Trigger docker compose rollout.

**Step 3: Validate live**

- `GET /health` => `200`
- `GET /readyz` => `200`
- `GET /api/v1/runtime/recovery/policy` includes `alert_dedupe_seconds`
- `POST /api/v1/runtime/recovery/run?...` => `200`
- Worker logs show periodic scheduler sweep.

**Step 4: Record evidence + push**

```bash
git add docs/operations/2026-02-25-live-recovery-rollout.md
git commit -m "docs: append phase17 rollout evidence"
git push origin phase17-recovery-scheduler
```
