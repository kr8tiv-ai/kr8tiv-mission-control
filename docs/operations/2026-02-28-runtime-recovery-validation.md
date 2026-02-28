# 2026-02-28 Runtime Recovery Validation

## Scope
- Mission Control API health aliases and runtime control-plane status.
- OpenClaw scope/auth readiness.
- Telegram poller stability (no `409 Conflict` churn).
- Arena + Notebook capability visibility.

## Validation Checklist
1. `GET /healthz` returns `200`.
2. `GET /api/v1/health` returns `200`.
3. `GET /api/v1/runtime/control-plane/status` returns `200` with capability map.
4. Agent-scoped task fetch works with valid token.
5. No repeated `missing scope: operator.*` in agent logs.
6. No repeated `getUpdates ... 409 Conflict` in bot logs during 30-minute soak.
7. Heartbeat throttling settings are present in runtime env.

## Notes
- This document is updated during live rollout and soak execution.

## 2026-02-28T12:58-13:05 (Local + Live Checkpoint)
- Local implementation/tests:
  - Runtime hardening suite passed:
    - mission-control targeted: `77 passed`
    - Jarvis targeted: `48 passed`
- Live endpoint checks (`76.13.106.100:8100`):
  - `GET /healthz` -> `200`
  - `GET /api/v1/health` -> `404` (compatibility alias not yet deployed)
  - `GET /api/v1/boards` -> `401` (expected without token)
- NotebookLM 50-question sweep:
  - status: `50/50` succeeded
  - artifact: `docs/operations/2026-02-28-notebooklm-50q-results.md`

## 2026-02-28T21:45-22:00 (Recovery Revalidation Checkpoint)
- Mission Control code hardening:
  - added explicit `capabilities.telegram_pollers` state to runtime control-plane API.
  - verification: `backend/tests/test_runtime_control_plane_status_api.py` passing.
- Live endpoint checks (`76.13.106.100:8100`):
  - `GET /healthz` -> `200`
  - `GET /api/v1/health` -> `200`
  - `GET /api/v1/runtime/control-plane/status` -> `401` (expected without admin token)
  - `GET /api/v1/boards` -> `401` (expected without token)
- NotebookLM 50-question sweep:
  - status: `0/50` succeeded
  - failure mode: `NotebookLM command timed out after 5s` for every query in this shell/runtime context
  - artifacts:
    - `docs/operations/2026-02-28-notebooklm-50q-results.md`
    - `backend/artifacts/notebooklm_50q_results.json`
  - next action: rerun with validated NotebookLM auth/profile runtime on deployment host.

## Pending Rollout Actions
1. Deploy backend image containing `capabilities.telegram_pollers` control-plane update.
2. Upgrade OpenClaw projects to security baseline release (`>=2026.2.26`) and verify no scope regressions.
3. Re-run NotebookLM 50q sweep on host with valid NotebookLM profile/auth and capture successful evidence.
4. Execute 30-minute bot/Telegram soak to confirm no recurring `409 Conflict` and no heartbeat storm churn.
