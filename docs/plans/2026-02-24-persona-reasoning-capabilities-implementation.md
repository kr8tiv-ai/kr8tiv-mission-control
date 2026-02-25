# Persona Integrity + Capabilities Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement hybrid persona governance, max-reasoning defaults, onboarding Q&A recommendations, tier quota enforcement, capabilities/install governance, secure device access, customer-owned backup reminders/options, and tenant self-access in Mission Control.

**Architecture:** Keep Mission Control as runtime policy authority while seeding reusable presets from git. Enforce persona precedence and reasoning policy in provisioning/sync paths, add onboarding Q&A + recommendation pipeline, enforce tier quotas for abilities/storage, add explicit capability/install/broker domains, and gate high-risk actions through owner approval plus audited break-glass override. Deliver incrementally with DB migrations + API + tests at each slice.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, OpenClaw provisioning services, Mission Control API routers.

---

### Task 1: Reasoning Resolution Policy Engine

**Files:**
- Create: `backend/app/services/openclaw/reasoning_policy.py`
- Test: `backend/tests/test_openclaw_reasoning_policy.py`

**Step 1: Write the failing tests**

```python
def test_resolve_reasoning_prefers_max_then_highest_then_default():
    assert resolve_reasoning_mode(["off", "medium", "high"], preferred="max") == "high"
    assert resolve_reasoning_mode(["off", "normal"], preferred="max") == "normal"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_openclaw_reasoning_policy.py -v`  
Expected: FAIL (module/function missing).

**Step 3: Write minimal implementation**

```python
def resolve_reasoning_mode(supported: list[str], preferred: str = "max") -> str:
    ...
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_openclaw_reasoning_policy.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/openclaw/reasoning_policy.py backend/tests/test_openclaw_reasoning_policy.py
git commit -m "feat: add reasoning mode resolution policy"
```

### Task 2: Enforce Reasoning Defaults in Provisioning Sync

**Files:**
- Modify: `backend/app/services/openclaw/constants.py`
- Modify: `backend/app/services/openclaw/provisioning.py`
- Test: `backend/tests/test_agent_provisioning_utils.py`

**Step 1: Write failing tests for heartbeat/config patch behavior**

```python
def test_patch_agent_heartbeats_sets_reasoning_defaults():
    # assert includeReasoning defaults true and thinkingDefault is policy-resolved
    ...
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_provisioning_utils.py -k reasoning -v`  
Expected: FAIL.

**Step 3: Implement minimal code**

```python
DEFAULT_HEARTBEAT_CONFIG["includeReasoning"] = True
# apply resolved thinkingDefault in config.patch payload
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_agent_provisioning_utils.py -k reasoning -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/openclaw/constants.py backend/app/services/openclaw/provisioning.py backend/tests/test_agent_provisioning_utils.py
git commit -m "feat: enforce max-capacity reasoning defaults in provisioning sync"
```

### Task 3: Persona Precedence Contract in Templates

**Files:**
- Modify: `backend/templates/BOARD_AGENTS.md.j2`
- Modify: `backend/templates/BOARD_SOUL.md.j2`
- Test: `backend/tests/test_agent_provisioning_utils.py`

**Step 1: Write failing template assertions**

```python
def test_agents_template_declares_persona_precedence():
    assert "SOUL.md > USER.md > IDENTITY.md > AGENTS.md" in rendered
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_provisioning_utils.py -k precedence -v`  
Expected: FAIL.

**Step 3: Implement minimal template changes**

```jinja2
- Persona precedence is non-negotiable: SOUL.md > USER.md > IDENTITY.md > AGENTS.md
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_agent_provisioning_utils.py -k precedence -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/templates/BOARD_AGENTS.md.j2 backend/templates/BOARD_SOUL.md.j2 backend/tests/test_agent_provisioning_utils.py
git commit -m "feat: enforce persona precedence in workspace contract"
```

### Task 4: Persona Checksum Baseline + Drift Records

**Files:**
- Create: `backend/app/models/agent_persona_integrity.py`
- Create: `backend/app/schemas/persona_integrity.py`
- Create: `backend/app/services/openclaw/persona_integrity_service.py`
- Create: `backend/migrations/versions/<new_revision>_add_agent_persona_integrity.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_persona_integrity_service.py`

**Step 1: Write failing service tests**

```python
def test_persona_integrity_service_detects_drift():
    ...
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_persona_integrity_service.py -v`  
Expected: FAIL.

**Step 3: Implement minimal model + service + migration**

```python
class AgentPersonaIntegrity(QueryModel, table=True):
    agent_id: UUID
    soul_sha256: str
    user_sha256: str
    identity_sha256: str
    agents_sha256: str
```

**Step 4: Run tests and migration checks**

Run: `cd backend && uv run pytest tests/test_persona_integrity_service.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/agent_persona_integrity.py backend/app/schemas/persona_integrity.py backend/app/services/openclaw/persona_integrity_service.py backend/migrations/versions backend/tests/test_persona_integrity_service.py backend/app/models/__init__.py
git commit -m "feat: add persona integrity checksum baseline and drift detection"
```

### Task 5: Persona Presets Catalog + Apply API

**Files:**
- Create: `backend/app/models/persona_presets.py`
- Create: `backend/app/schemas/persona_presets.py`
- Create: `backend/app/api/persona_presets.py`
- Modify: `backend/app/main.py`
- Create: `backend/migrations/versions/<new_revision>_add_persona_presets.py`
- Test: `backend/tests/test_persona_presets_api.py`

**Step 1: Write failing API tests**

```python
def test_apply_persona_preset_updates_agent_templates():
    ...
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_persona_presets_api.py -v`  
Expected: FAIL.

**Step 3: Implement minimal CRUD + apply endpoint**

```python
@router.post("/agents/{agent_id}/apply")
async def apply_preset(...):
    # update identity_profile, identity_template, soul_template
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_persona_presets_api.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/persona_presets.py backend/app/schemas/persona_presets.py backend/app/api/persona_presets.py backend/app/main.py backend/migrations/versions backend/tests/test_persona_presets_api.py
git commit -m "feat: add persona preset catalog and apply flow"
```

### Task 6: Onboarding Q&A Recommendations + Personalized Defaults

**Files:**
- Modify: `backend/app/schemas/board_onboarding.py`
- Modify: `backend/app/api/board_onboarding.py`
- Create: `backend/app/models/onboarding_recommendations.py`
- Create: `backend/migrations/versions/<new_revision>_add_onboarding_recommendations.py`
- Test: `backend/tests/test_board_onboarding_recommendations.py`

**Step 1: Write failing tests**

```python
def test_onboarding_qa_generates_persona_and_ability_recommendation():
    ...

def test_personalized_flow_defaults_voice_and_uplay_chromium_capability():
    ...
```

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/test_board_onboarding_recommendations.py -v`  
Expected: FAIL.

**Step 3: Implement minimal recommendation flow**

```python
# Store onboarding answers and emit recommended preset + ability bundle
# Personalized mode: default voice + computer automation profile
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_board_onboarding_recommendations.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/schemas/board_onboarding.py backend/app/api/board_onboarding.py backend/app/models/onboarding_recommendations.py backend/migrations/versions backend/tests/test_board_onboarding_recommendations.py
git commit -m "feat: add onboarding QA recommendations with personalized defaults"
```

### Task 7: Capabilities Catalog (Skills, Libraries, Devices)

**Files:**
- Create: `backend/app/models/capabilities.py`
- Create: `backend/app/schemas/capabilities.py`
- Create: `backend/app/api/capabilities.py`
- Modify: `backend/app/main.py`
- Create: `backend/migrations/versions/<new_revision>_add_capabilities_tables.py`
- Test: `backend/tests/test_capabilities_api.py`

**Step 1: Write failing API tests**

```python
def test_create_skill_library_device_records_requires_admin():
    ...
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_capabilities_api.py -v`  
Expected: FAIL.

**Step 3: Implement minimal endpoints and models**

```python
# skills, libraries, devices with risk and scope metadata
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_capabilities_api.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/capabilities.py backend/app/schemas/capabilities.py backend/app/api/capabilities.py backend/app/main.py backend/migrations/versions backend/tests/test_capabilities_api.py
git commit -m "feat: add capabilities catalogs for skills libraries and devices"
```

### Task 8: Installations + Owner Ask-First + Break-Glass

**Files:**
- Create: `backend/app/models/installations.py`
- Create: `backend/app/schemas/installations.py`
- Create: `backend/app/api/installations.py`
- Create: `backend/app/models/override_sessions.py`
- Modify: `backend/app/main.py`
- Create: `backend/migrations/versions/<new_revision>_add_installations_and_override.py`
- Test: `backend/tests/test_installations_policy_api.py`

**Step 1: Write failing policy tests**

```python
def test_install_request_requires_owner_approval_by_default():
    ...

def test_break_glass_requires_reason_and_ttl():
    ...
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_installations_policy_api.py -v`  
Expected: FAIL.

**Step 3: Implement minimal approval + override policy**

```python
# default mode: ask_first
# break-glass: owner/admin only, reason required, TTL enforced
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_installations_policy_api.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/installations.py backend/app/schemas/installations.py backend/app/api/installations.py backend/app/models/override_sessions.py backend/app/main.py backend/migrations/versions backend/tests/test_installations_policy_api.py
git commit -m "feat: add install governance with ask-first and break-glass controls"
```

### Task 9: Tier Quotas (Ability Slots + Storage Limits)

**Files:**
- Create: `backend/app/models/tier_quotas.py`
- Create: `backend/app/schemas/tier_quotas.py`
- Create: `backend/app/api/tier_quotas.py`
- Modify: `backend/app/api/installations.py`
- Modify: `backend/app/main.py`
- Create: `backend/migrations/versions/<new_revision>_add_tier_quota_tables.py`
- Test: `backend/tests/test_tier_quota_enforcement.py`

**Step 1: Write failing tests**

```python
def test_install_blocked_when_ability_slots_exhausted():
    ...

def test_storage_over_quota_returns_clear_message():
    ...
```

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/test_tier_quota_enforcement.py -v`  
Expected: FAIL.

**Step 3: Implement minimal quota enforcement**

```python
# enforce max abilities and storage per tier before install/enable
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_tier_quota_enforcement.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/tier_quotas.py backend/app/schemas/tier_quotas.py backend/app/api/tier_quotas.py backend/app/api/installations.py backend/app/main.py backend/migrations/versions backend/tests/test_tier_quota_enforcement.py
git commit -m "feat: enforce tier quotas for abilities and storage"
```

### Task 10: Customer-Owned Backup Reminder Workflow + Destination Options

**Files:**
- Create: `backend/app/models/backups.py`
- Create: `backend/app/schemas/backups.py`
- Create: `backend/app/api/backups.py`
- Create: `backend/app/services/backups/reminder_service.py`
- Modify: `backend/app/main.py`
- Create: `backend/migrations/versions/<new_revision>_add_backup_reminder_tables.py`
- Test: `backend/tests/test_backup_reminders_api.py`

**Step 1: Write failing tests**

```python
def test_twice_weekly_backup_reminder_emits_warning_when_unconfirmed():
    ...

def test_backup_confirmation_records_destination_without_payload():
    ...

def test_backup_confirmation_accepts_multiple_destination_types():
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_backup_reminders_api.py -v`  
Expected: FAIL.

**Step 3: Implement minimal reminder + confirmation endpoints**

```python
# reminder channels: ui + telegram/whatsapp fallback
# confirmation stores metadata only
# destination supports local drive, external drive, customer cloud, manual export
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_backup_reminders_api.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/backups.py backend/app/schemas/backups.py backend/app/api/backups.py backend/app/services/backups/reminder_service.py backend/app/main.py backend/migrations/versions backend/tests/test_backup_reminders_api.py
git commit -m "feat: add customer-owned backup reminders and confirmations"
```

### Task 11: Change Request Workflow

**Files:**
- Create: `backend/app/models/change_requests.py`
- Create: `backend/app/schemas/change_requests.py`
- Create: `backend/app/api/change_requests.py`
- Modify: `backend/app/main.py`
- Create: `backend/migrations/versions/<new_revision>_add_change_requests.py`
- Test: `backend/tests/test_change_requests_api.py`

**Step 1: Write failing tests**

```python
def test_customer_can_submit_and_track_change_request():
    ...
```

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/test_change_requests_api.py -v`  
Expected: FAIL.

**Step 3: Implement minimal request lifecycle endpoints**

```python
# submitted -> triage -> approved/rejected -> applied
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_change_requests_api.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models/change_requests.py backend/app/schemas/change_requests.py backend/app/api/change_requests.py backend/app/main.py backend/migrations/versions backend/tests/test_change_requests_api.py
git commit -m "feat: add customer change request workflow"
```

### Task 12: Tenant Self-Access Baseline

**Files:**
- Create: `backend/app/api/tenant_access.py`
- Create: `backend/app/schemas/tenant_access.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_tenant_access_api.py`

**Step 1: Write failing tests**

```python
def test_customer_can_fetch_own_mission_control_access_context():
    ...
```

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/test_tenant_access_api.py -v`  
Expected: FAIL.

**Step 3: Implement minimal self-access endpoint**

```python
@router.get("/tenant/self")
async def tenant_self(...):
    # returns tenant-scoped mission-control access context
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_tenant_access_api.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/tenant_access.py backend/app/schemas/tenant_access.py backend/app/main.py backend/tests/test_tenant_access_api.py
git commit -m "feat: add tenant self-access endpoint baseline"
```

### Task 13: Cross-Repo Schema Alignment for Harness + Presets

**Files:**
- Modify: `../kr8tivclaw/src/compiler/schema.ts`
- Modify: `../kr8tivclaw/src/compiler/harness-compiler.ts`
- Modify: `../kr8tivclaw/src/templates/workspace.ts`
- Test: `../kr8tivclaw/tests/schema-validation.test.ts`
- Test: `../kr8tivclaw/tests/harness-golden.test.ts`
- Modify: `../kr8tiv-team-execution-resilience/templates/profiles/*.profile.json`

**Step 1: Write failing tests for new schema fields**

```ts
expect(parsed.reasoningPolicy.default).toBe("max")
expect(parsed.persona.presetRef).toBeDefined()
expect(parsed.onboarding.recommendationEnabled).toBe(true)
```

**Step 2: Run tests**

Run: `cd ../kr8tivclaw && npm test -- --runInBand schema-validation.test.ts harness-golden.test.ts`  
Expected: FAIL.

**Step 3: Implement minimal schema/template extensions**

```ts
reasoningPolicy: { default: "max", fallbackBehavior: "highest_or_model_default" }
persona: { presetRef: "...", mode: "team|individual" }
onboarding: { recommendationEnabled: true, personalizedDefaults: ["voice", "uplay_chromium"] }
```

**Step 4: Run tests**

Run: `cd ../kr8tivclaw && npm test -- --runInBand schema-validation.test.ts harness-golden.test.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ../kr8tivclaw/src/compiler/schema.ts ../kr8tivclaw/src/compiler/harness-compiler.ts ../kr8tivclaw/src/templates/workspace.ts ../kr8tivclaw/tests/schema-validation.test.ts ../kr8tivclaw/tests/harness-golden.test.ts ../kr8tiv-team-execution-resilience/templates/profiles
git commit -m "feat: align harness schema with persona and reasoning governance"
```

### Task 14: Documentation + Runbook Updates

**Files:**
- Modify: `docs/openclaw_15_point_harness.md`
- Modify: `docs/production/README.md`
- Modify: `docs/README.md`
- Create: `docs/policy/persona-integrity-protocol.md`
- Create: `docs/security/device-access-broker.md`
- Create: `docs/operations/customer-backup-policy.md`

**Step 1: Write failing doc assertions (link presence checks)**

```python
def test_docs_reference_persona_integrity_protocol():
    ...
```

**Step 2: Run docs test**

Run: `cd backend && uv run pytest tests -k docs -v`  
Expected: FAIL or skip until checks added.

**Step 3: Implement docs changes**

```md
- Add reasoning default policy.
- Add ask-first install policy.
- Add backup reminder and ownership policy.
- Add onboarding Q&A recommendation and tier quota policy.
```

**Step 4: Run docs checks**

Run: `cd backend && uv run pytest tests -k docs -v`  
Expected: PASS (or no doc-test failures).

**Step 5: Commit**

```bash
git add docs/openclaw_15_point_harness.md docs/production/README.md docs/README.md docs/policy/persona-integrity-protocol.md docs/security/device-access-broker.md docs/operations/customer-backup-policy.md
git commit -m "docs: add persona reasoning capabilities and backup runbooks"
```

## Final Verification Gate

Run from `backend/`:

```bash
uv run pytest -v
```

Expected:
- All new tests pass.
- Existing provisioning, auth, and agent lifecycle tests remain green.

Then run from `../kr8tivclaw/`:

```bash
npm test -- --runInBand
```

Expected:
- harness schema + golden outputs pass with new fields.
