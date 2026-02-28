# Incident Response Runbook

## Purpose
Operator runbook for runtime instability incidents affecting Mission Control, OpenClaw agents, Telegram ingress, and arena/notebook workflows.

## Immediate Triage Checklist
1. Verify API liveness:
   - `GET /healthz`
   - `GET /api/v1/health`
   - `GET /readyz`
2. Verify control-plane readiness:
   - `GET /api/v1/runtime/control-plane/status`
3. Verify auth posture:
   - check logs for `agent auth invalid token`
   - check logs for `missing scope: operator.*`
4. Verify Telegram poller health:
   - check logs for `getUpdates ... 409 Conflict`
   - ensure one poller process per bot token.

## Telegram 409 Conflict Response
1. Stop all duplicate bot pollers sharing the same token.
2. Keep one canonical poller process/container.
3. Confirm no recurring `409 Conflict` for 30 minutes.
4. If recurrence persists, rotate affected bot token and redeploy.

## Mission Control Auth Desync Response
1. Regenerate/sync agent tokens between Mission Control and agent runtimes.
2. Re-run task-fetch probe from each agent.
3. Confirm `/api/v1/agent/boards/{board_id}/tasks` returns success for valid token.
4. Confirm invalid-token path remains rejected with deterministic error.

## Heartbeat Storm Mitigation
1. Confirm current runtime flags:
   - `HEARTBEAT_SINGLEFLIGHT_ENABLED=true`
   - `HEARTBEAT_MIN_INTERVAL_SECONDS>=15`
   - `HEARTBEAT_JITTER_SECONDS>=1`
2. Validate reduced duplicate heartbeat churn in logs.
3. If still storming, temporarily increase `HEARTBEAT_MIN_INTERVAL_SECONDS` and redeploy.

## Degraded Mode Policy
1. If NotebookLM path is unstable:
   - keep task execution operational
   - report notebook gate state as `retryable/misconfig/hard_fail`
   - avoid blocking non-notebook task modes.
2. If ingress is noisy:
   - keep owner-directed processing enabled
   - block self-message loops
   - apply duplicate-message suppression.

## Rollback Playbook
1. Revert to last known-good image tags for Mission Control and agent projects.
2. Disable newly enabled features via env:
   - `NOTEBOOKLM_ENABLED=0` (if applicable)
   - `GSD_SPEC_ENABLED=0` (if applicable)
3. Restore previous env bundle from secure backup.
4. Re-run baseline smoke checks (`healthz`, runtime status, agent task fetch, Telegram group response).

## Post-Incident Evidence
1. Record timeline, root cause, and blast radius.
2. Attach relevant logs and endpoint checks.
3. Record rollback or mitigation actions.
4. Add prevention task to roadmap backlog with owner and due date.

