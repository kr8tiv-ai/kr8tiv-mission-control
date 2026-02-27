# Phase 15 Runtime Hardening + Autonomy Guardrails Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make live operations deterministic after recovery by hardening deployment reproducibility, disk guardrails, agent continuity checks, and GSD execution telemetry.

**Architecture:** Keep control-plane behavior in Mission Control and move deploy/runtime safety into explicit contracts: immutable image tags, health gating, capacity alarms, and self-healing orchestration checks.

**Tech Stack:** FastAPI, SQLModel, Alembic, Docker Compose, GHCR, pytest.

---

### Task 1: Immutable Runtime Image Policy

**Files:**
- Create: `docs/production/runtime-image-policy.md`
- Modify: `compose.yml`
- Modify: `scripts/release_images.sh` (create if missing)

**Step 1: Define image policy**

Enforce backend/frontend image tags derived from git SHA + timestamp. Forbid non-versioned floating tags in production compose.

**Step 2: Add release script**

Implement script that builds and publishes backend + frontend images to GHCR and outputs resolved tags for deployment.

**Step 3: Verify**

Run local dry-run mode to print resolved tags and compose substitutions.

**Step 4: Commit**

```bash
git add docs/production/runtime-image-policy.md compose.yml scripts/release_images.sh
git commit -m "ops: enforce immutable ghcr image policy for production runtime"
```

### Task 2: Disk Pressure Guardrails

**Files:**
- Create: `backend/app/services/runtime/disk_guard.py`
- Create: `backend/app/api/runtime_ops.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_disk_guard.py`

**Step 1: Write failing tests**

Validate thresholds and severity mapping for warning/critical disk states.

**Step 2: Implement guard service**

Add service that reports disk usage + recommended action envelope.

**Step 3: Expose runtime ops endpoint**

Add authenticated endpoint to surface current guard status in Mission Control.

**Step 4: Verify**

```bash
cd backend && uv run pytest tests/test_disk_guard.py -v
```

**Step 5: Commit**

```bash
git add backend/app/services/runtime/disk_guard.py backend/app/api/runtime_ops.py backend/app/main.py backend/tests/test_disk_guard.py
git commit -m "feat: add disk pressure guardrails and runtime ops surface"
```

### Task 3: Agent Continuity Probe Contract

**Files:**
- Create: `backend/app/services/agent_continuity.py`
- Create: `backend/app/api/agent_continuity.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_agent_continuity.py`

**Step 1: Write failing tests**

Assert continuity report identifies:
- alive agents
- stale heartbeats
- unreachable agent runtimes

**Step 2: Implement continuity service + API**

Provide board-scoped continuity snapshots suitable for automation checks.

**Step 3: Verify**

```bash
cd backend && uv run pytest tests/test_agent_continuity.py -v
```

**Step 4: Commit**

```bash
git add backend/app/services/agent_continuity.py backend/app/api/agent_continuity.py backend/app/main.py backend/tests/test_agent_continuity.py
git commit -m "feat: add agent continuity probe contract"
```

### Task 4: GSD Run Telemetry for Stage Progress

**Files:**
- Create: `backend/app/models/gsd_runs.py`
- Create: `backend/app/schemas/gsd_runs.py`
- Create: `backend/app/api/gsd_runs.py`
- Create: `backend/migrations/versions/<new_revision>_add_gsd_runs.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_gsd_runs_api.py`

**Step 1: Write failing API tests**

Cover create/update/read of run status by stage:
- planning
- implementation
- rollout
- validation
- hardening

**Step 2: Implement model + API + migration**

Track iteration status, owner approval points, and rollout verification evidence links.

**Step 3: Verify**

```bash
cd backend && uv run pytest tests/test_gsd_runs_api.py -v
```

**Step 4: Commit**

```bash
git add backend/app/models/gsd_runs.py backend/app/schemas/gsd_runs.py backend/app/api/gsd_runs.py backend/migrations/versions backend/app/models/__init__.py backend/app/main.py backend/tests/test_gsd_runs_api.py
git commit -m "feat: add gsd run telemetry and stage tracking"
```

### Task 5: Full Verification + Production Rollout

**Files:**
- Modify: `docs/operations/2026-02-25-live-recovery-rollout.md` (append rollout evidence)

**Step 1: Run complete backend verification**

```bash
cd backend && uv run pytest tests -q
cd backend && uv run alembic heads
```

**Step 2: Run frontend verification**

```bash
cd frontend && npm test
cd frontend && npm run build
```

**Step 3: Deploy with immutable tags**

Use release script output tags and verify live health endpoints and OpenAPI route presence.

**Step 4: Commit + Push**

```bash
git add docs/operations/2026-02-25-live-recovery-rollout.md
git commit -m "docs: append phase15 rollout evidence"
git push origin main
```
