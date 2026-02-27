# Phase 27 Rollout Gate + Auto-Rollback Implementation

Date: 2026-02-27
Owner: Mission Control Runtime

## Objective

Implement CI-enforced runtime health verification and configurable rollback triggering in the image publish pipeline.

## Changes

### 1) New rollout gate script

File:
- `scripts/ci/rollout_health_gate.py`

Capabilities:
1. Parse and normalize probe URLs.
2. Retry runtime probes with bounded timeout.
3. Emit deterministic status (`passed|failed|skipped`).
4. Trigger optional rollback command on failed status.
5. Persist JSON evidence and env summaries.

### 2) Tests (TDD)

File:
- `backend/tests/test_rollout_health_gate.py`

Coverage:
1. URL parsing normalization/dedupe.
2. Skipped behavior with no URLs.
3. Retry-until-success flow.
4. Failed gate rollback trigger.
5. Env summary output contract.

### 3) Publish workflow wiring

File:
- `.github/workflows/publish-mission-control-images.yml`

Added:
1. Post-publish gate execution step:
   - `RUNTIME_HEALTH_URLS`
   - `RUNTIME_ROLLBACK_COMMAND`
2. Always-on artifact upload:
   - `artifacts/rollout/health-gate.json`
   - `artifacts/rollout/health-gate.env`

### 4) Operational docs

Files:
- `docs/production/runtime-image-policy.md`
- `docs/openclaw_15_point_harness.md`
- `docs/operations/2026-02-27-notebooklm-phase27-qna.md`

Updates:
1. Added gate contracts and failure semantics.
2. Added Phase 27 runtime harness overlay.
3. Captured NotebookLM rationale and conversation IDs.

## Verification commands

```bash
cd backend
UV_PROJECT_ENVIRONMENT=.venv-test uv run pytest tests/test_rollout_health_gate.py -q
```

Expected:
- 5 passing tests for gate/rollback semantics.

## Follow-up actions

1. Configure repository secrets:
   - `RUNTIME_HEALTH_URLS`
   - `RUNTIME_ROLLBACK_COMMAND`
2. Validate first live publish run artifact.
3. Add host-side rollback command script once stable shell access is re-established.
