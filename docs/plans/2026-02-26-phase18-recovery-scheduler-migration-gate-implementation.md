# Phase 18 Recovery Scheduler Migration Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent scheduler startup race errors by running periodic recovery sweeps only after database migrations are confirmed at Alembic head.

**Architecture:** Add a dedicated migration gate helper that compares `alembic_version` in DB to repository Alembic head, then integrate that check into queue worker scheduler tick logic. Keep queue dispatch behavior unchanged when gate is closed.

**Tech Stack:** FastAPI runtime services, SQLAlchemy/SQLModel async sessions, Alembic metadata, pytest.

---

### Task 1: Add Migration Head Helper + Gate Service

**Files:**
- Modify: `backend/app/db/session.py`
- Create: `backend/app/services/runtime/migration_gate.py`
- Test: `backend/tests/test_recovery_migration_gate.py`

**Step 1: Write failing tests**

Add tests for:

```python
async def test_gate_ready_when_db_revision_matches_head():
    ...

async def test_gate_not_ready_when_revision_differs():
    ...

async def test_gate_caches_successful_readiness():
    ...
```

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_recovery_migration_gate.py -q`

Expected: FAIL (module/helper missing).

**Step 3: Implement minimal helpers**

- Add `get_alembic_head_revision()` in `db/session.py`.
- Add runtime gate module with:
  - `is_scheduler_migration_ready()`
  - `reset_scheduler_migration_gate()` (test hook)
  - internal DB revision fetch from `alembic_version`.
- Cache readiness once `True`.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_recovery_migration_gate.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/db/session.py backend/app/services/runtime/migration_gate.py backend/tests/test_recovery_migration_gate.py
git commit -m "feat: add alembic head migration gate for recovery scheduler"
```

### Task 2: Integrate Gate into Queue Worker Scheduler Path

**Files:**
- Modify: `backend/app/services/queue_worker.py`
- Modify: `backend/tests/test_queue_worker_recovery_scheduler.py`

**Step 1: Write failing integration test**

Add:

```python
async def test_run_recovery_scheduler_once_skips_when_migrations_pending():
    ...
```

**Step 2: Run tests to verify fail**

Run:
`cd backend && uv run pytest tests/test_queue_worker_recovery_scheduler.py -q`

Expected: FAIL (gate not yet wired).

**Step 3: Implement minimal integration**

- In `run_recovery_scheduler_once()`:
  1. respect `recovery_loop_enabled`
  2. call migration gate
  3. if gate closed, return without scheduler run
  4. if open, run scheduler as before.

**Step 4: Re-run tests**

Run:
`cd backend && uv run pytest tests/test_queue_worker_recovery_scheduler.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/queue_worker.py backend/tests/test_queue_worker_recovery_scheduler.py
git commit -m "feat: gate recovery scheduler start on migration readiness"
```

### Task 3: Verification + Docs Update

**Files:**
- Modify: `docs/openclaw_15_point_harness.md`
- Modify: `docs/operations/2026-02-25-live-recovery-rollout.md`

**Step 1: Run focused verification**

Run:
`cd backend && uv run pytest tests/test_recovery_migration_gate.py tests/test_queue_worker_recovery_scheduler.py tests/test_recovery_scheduler.py tests/test_recovery_engine.py tests/test_recovery_ops_api.py -q`

Expected: PASS.

**Step 2: Add Phase 18 harness checks**

Add startup migration-gate validation:
- scheduler defers while migration pending
- scheduler runs after migration head reached
- no startup `UndefinedColumn` loop noise.

**Step 3: Commit + Push**

```bash
git add docs/openclaw_15_point_harness.md docs/operations/2026-02-25-live-recovery-rollout.md
git commit -m "docs: add phase18 migration gate validation"
git push origin phase18-migration-gate
```
