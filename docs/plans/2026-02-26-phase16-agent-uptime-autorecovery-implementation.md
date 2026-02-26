# Phase 16 Agent Uptime Autorecovery + Alert Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure Mission Control continuously detects down/stale agents, runs deterministic recovery actions, and notifies owners in Telegram/WhatsApp/UI with auditable incident records.

**Architecture:** Build on the existing `agent_continuity` contract by adding an organization-scoped recovery policy, incident tracking, a bounded autorecovery engine, and explicit alert routing. Keep all recovery actions behind policy + cooldown guards to prevent restart storms.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, OpenClaw gateway RPC, channel ingress policy.

---

### Task 1: Recovery Policy + Incident Data Model

**Files:**
- Create: `backend/app/models/recovery_policies.py`
- Create: `backend/app/models/recovery_incidents.py`
- Create: `backend/migrations/versions/<new_revision>_add_recovery_policy_incidents.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_recovery_models.py`

**Step 1: Write failing model tests**

```python
def test_recovery_policy_defaults_enable_autorestart_with_cooldown():
    ...

def test_recovery_incident_status_lifecycle_fields_present():
    ...
```

**Step 2: Run tests to verify fail**

Run: `cd backend && uv run pytest tests/test_recovery_models.py -v`  
Expected: FAIL (missing models/migration).

**Step 3: Implement minimal models + migration**

```python
class RecoveryPolicy(QueryModel, table=True):
    organization_id: UUID
    enabled: bool = True
    stale_after_seconds: int = 900
    max_restarts_per_hour: int = 3
    cooldown_seconds: int = 300
    alert_telegram: bool = True
    alert_whatsapp: bool = True
```

```python
class RecoveryIncident(QueryModel, table=True):
    organization_id: UUID
    board_id: UUID
    agent_id: UUID
    status: str  # detected|recovering|recovered|failed|suppressed
    reason: str
    action: str | None
    attempts: int = 0
```

**Step 4: Re-run tests**

Run: `cd backend && uv run pytest tests/test_recovery_models.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/recovery_policies.py backend/app/models/recovery_incidents.py backend/migrations/versions backend/app/models/__init__.py backend/tests/test_recovery_models.py
git commit -m "feat: add recovery policy and incident persistence models"
```

### Task 2: Autorecovery Engine

**Files:**
- Create: `backend/app/services/runtime/recovery_engine.py`
- Modify: `backend/app/services/agent_continuity.py`
- Test: `backend/tests/test_recovery_engine.py`

**Step 1: Write failing recovery tests**

```python
def test_recovery_engine_detects_stale_and_queues_recovery():
    ...

def test_recovery_engine_respects_cooldown_and_attempt_limits():
    ...

def test_recovery_engine_marks_failed_when_gateway_recovery_errors():
    ...
```

**Step 2: Run tests to verify fail**

Run: `cd backend && uv run pytest tests/test_recovery_engine.py -v`  
Expected: FAIL.

**Step 3: Implement minimal engine**

```python
class RecoveryEngine:
    async def evaluate_board(self, *, board_id: UUID) -> list[RecoveryIncident]:
        # 1) continuity snapshot
        # 2) policy checks/cooldowns
        # 3) call recovery action
        # 4) persist incident state
        ...
```

Recovery action priority:
1. Session rebind/check via gateway.
2. Heartbeat/config resync.
3. Mark failed and emit alert candidate.

**Step 4: Re-run tests**

Run: `cd backend && uv run pytest tests/test_recovery_engine.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/runtime/recovery_engine.py backend/app/services/agent_continuity.py backend/tests/test_recovery_engine.py
git commit -m "feat: add bounded agent autorecovery engine"
```

### Task 3: Recovery API Surface

**Files:**
- Create: `backend/app/api/recovery_ops.py`
- Create: `backend/app/schemas/recovery_ops.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_recovery_ops_api.py`

**Step 1: Write failing API tests**

```python
def test_get_recovery_policy_requires_admin():
    ...

def test_update_recovery_policy_persists_limits():
    ...

def test_run_recovery_now_returns_incident_summary():
    ...
```

**Step 2: Run tests to verify fail**

Run: `cd backend && uv run pytest tests/test_recovery_ops_api.py -v`  
Expected: FAIL.

**Step 3: Implement minimal endpoints**

```python
GET  /api/v1/runtime/recovery/policy
PUT  /api/v1/runtime/recovery/policy
POST /api/v1/runtime/recovery/run
GET  /api/v1/runtime/recovery/incidents
```

**Step 4: Re-run tests**

Run: `cd backend && uv run pytest tests/test_recovery_ops_api.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/recovery_ops.py backend/app/schemas/recovery_ops.py backend/app/main.py backend/tests/test_recovery_ops_api.py
git commit -m "feat: add runtime recovery policy and incident API"
```

### Task 4: Alert Routing (Telegram/WhatsApp/UI)

**Files:**
- Create: `backend/app/services/runtime/recovery_alerts.py`
- Modify: `backend/app/services/channel_ingress.py`
- Modify: `backend/app/services/webhooks/dispatch.py`
- Test: `backend/tests/test_recovery_alert_routing.py`

**Step 1: Write failing alert-routing tests**

```python
def test_recovery_alert_prefers_enabled_owner_channels():
    ...

def test_whatsapp_respects_phase_gates():
    ...

def test_ui_alert_fallback_when_channel_delivery_fails():
    ...
```

**Step 2: Run tests to verify fail**

Run: `cd backend && uv run pytest tests/test_recovery_alert_routing.py -v`  
Expected: FAIL.

**Step 3: Implement minimal alert broker**

```python
# Compose incident payload + route by policy:
# telegram -> whatsapp -> ui incident feed fallback
```

**Step 4: Re-run tests**

Run: `cd backend && uv run pytest tests/test_recovery_alert_routing.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/runtime/recovery_alerts.py backend/app/services/channel_ingress.py backend/app/services/webhooks/dispatch.py backend/tests/test_recovery_alert_routing.py
git commit -m "feat: route recovery alerts to owner channels with fallback"
```

### Task 5: Full Verification + Rollout Evidence

**Files:**
- Modify: `docs/openclaw_15_point_harness.md`
- Modify: `docs/operations/2026-02-25-live-recovery-rollout.md`

**Step 1: Run backend full verification**

```bash
cd backend
$env:UV_PROJECT_ENVIRONMENT='.venv-test'
uv run pytest tests -q
uv run alembic heads
```

**Step 2: Run frontend verification**

```bash
cd frontend
npm test
npm run build
```

**Step 3: Live rollout + checks**

Deploy immutable tags and verify:
- `/health`
- `/readyz`
- `/api/v1/runtime/recovery/policy`
- `/api/v1/runtime/recovery/incidents`
- board continuity + recovery run endpoints

**Step 4: Append operational evidence**

Record:
- image tags
- action IDs/timestamps
- endpoint status codes
- one simulated stale-agent recovery run result

**Step 5: Commit + Push**

```bash
git add docs/openclaw_15_point_harness.md docs/operations/2026-02-25-live-recovery-rollout.md
git commit -m "docs: append phase16 recovery rollout evidence"
git push origin main
```
