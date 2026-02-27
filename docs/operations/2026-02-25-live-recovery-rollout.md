# 2026-02-25 Live Recovery + Rollout Record

## Summary

Mission Control was recovered from a failed rollout state and brought back to stable operation with the new control-plane capabilities live.

## Root Cause

1. Hostinger `docker_compose_up` path attempted image pulls and did not reliably build from `build:` contexts during our rollout sequence.
2. VPS disk pressure escalated to API failures (`No space left on device`) and caused unstable Docker project actions.
3. Mission Control compose had been changed to non-pullable local tags, which increased rollout fragility.

## Recovery Actions

1. Merged and pushed code to `main`:
   - `kr8tiv-mission-control` @ `2254f3b948733582f98b64f7baefa067cefa7dda`
   - `kr8tivclaw` @ `1b06fd9`
   - `kr8tiv-team-execution-resilience` @ `ebf73da`
2. Gained emergency shell access to VPS and reclaimed disk:
   - `docker image prune -af`
   - `docker builder prune -af`
   - `docker container prune -f`
   - Result: root filesystem from ~97% used to ~78% used (~44 GB free).
3. Recovered Mission Control from `/docker/openclaw-mission-control`:
   - Checked out commit `2254f3b948733582f98b64f7baefa067cefa7dda`
   - Pulled backend image from GHCR
   - Built frontend image on-server
   - Brought up stack with Docker Compose
4. Published immutable GHCR images and pinned compose runtime to them:
   - Backend: `ghcr.io/matt-aurora-ventures/jarvis:kr8tiv-mc-backend-2254f3b-20260225t1144z`
   - Frontend: `ghcr.io/matt-aurora-ventures/jarvis:kr8tiv-mc-frontend-2254f3b-20260225t1943z`

## Live Verification

1. Public health checks:
   - `http://76.13.106.100:8100/health` => `200`
   - `http://76.13.106.100:3100` => `200`
   - `http://76.13.106.100:48650/health` => `200`
   - `http://76.13.106.100:48651/health` => `200`
   - `http://76.13.106.100:48652/health` => `200`
   - `http://76.13.106.100:48653/health` => `200`
2. Mission Control containers all running:
   - backend, db, frontend, redis, webhook-worker
3. New control-plane surface present in live OpenAPI:
   - `/api/v1/runtime/packs/resolve` (`GET`)
   - `/api/v1/packs` (`POST`)
   - `/api/v1/persona-presets` (`GET`, `POST`)
   - `/api/v1/tier-quotas` (`GET`)
   - `/api/v1/tenant/self` (`GET`)
   - `/api/v1/backups/reminder` (`GET`)
4. Auth + board API checks passed with local auth bearer token:
   - `/api/v1/auth/bootstrap` (`POST`) => `200`
   - `/api/v1/boards` (`GET`) => `200`
   - `/api/v1/boards/{board_id}/tasks` (`GET`) => `200`

## Artifacts

Operational logs and API snapshots were captured under:
- `artifacts/ops/`

Notable files:
- `vps-cleanup-20260225T1932Z.log`
- `vps-recover-mission-control-20260225T1943Z.log`
- `vps-frontend-ghcr-hardening-20260225T1952Z.log`

## 2026-02-25 Rollout Update (Task 2/3)

Latest runtime rollout was executed through Hostinger Docker Manager for:
- Commit: `bcf26cda7741d7cb6c471cb328e12ddca1727a2d`
- Backend/Webhook image: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:bcf26cd`
- Frontend image: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-frontend:bcf26cd`

Verification snapshot:
1. Hostinger action `docker_compose_up` completed with `success` at `2026-02-25T21:57:32Z`.
2. Mission Control containers running on new immutable tags:
   - `kr8tiv-mission-control-backend-1`
   - `kr8tiv-mission-control-db-1`
   - `kr8tiv-mission-control-frontend-1`
   - `kr8tiv-mission-control-redis-1`
   - `kr8tiv-mission-control-webhook-worker-1`
3. Live endpoint checks:
   - `http://76.13.106.100:8100/health` => `200`
   - `http://76.13.106.100:8100/readyz` => `200`
   - `http://76.13.106.100:3100` => `200`
   - OpenAPI paths present:
     - `/api/v1/runtime/ops/disk-guard`
     - `/api/v1/boards/{board_id}/agent-continuity`
     - `/api/v1/runtime/packs/resolve`
4. Agent runtime TCP checks passed:
   - `76.13.106.100:48650`
   - `76.13.106.100:48651`
   - `76.13.106.100:48652`
   - `76.13.106.100:48653`

## 2026-02-25 Rollout Update (Task 4)

After Phase 15 Task 4 merge, runtime was rolled again to immutable SHA tags:
- Commit: `134439b85180cfb1ed9708babb0eecea62577657`
- Backend/Webhook image: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:134439b`
- Frontend image: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-frontend:134439b`

Verification snapshot:
1. Hostinger action `docker_compose_up` completed with `success` at `2026-02-25T22:14:12Z`.
2. Mission Control containers running on `134439b` image tags:
   - backend, db, frontend, redis, webhook-worker
3. Public checks:
   - `http://76.13.106.100:8100/health` => `200`
   - `http://76.13.106.100:8100/readyz` => `200`
   - `http://76.13.106.100:3100` => `200`
4. OpenAPI checks:
   - `/api/v1/runtime/ops/disk-guard` present
   - `/api/v1/boards/{board_id}/agent-continuity` present
   - `/api/v1/gsd-runs` present
   - `/api/v1/gsd-runs/{run_id}` present

## 2026-02-26 Rollout Update (Task 5 Verification Closeout)

Phase 15 Task 5 verification was completed end-to-end from the `main` branch.

Verification snapshot:
1. Backend full-suite checks:
   - `UV_PROJECT_ENVIRONMENT=.venv-test uv run pytest tests -q` => `401 passed, 1 xfailed, 1 warning`
   - `UV_PROJECT_ENVIRONMENT=.venv-test uv run alembic heads` => `8c4e2b1d9f0a (head)`
2. Frontend full-suite checks:
   - `npm test` => `21 passed` test files, `81 passed` tests
   - `npm run build` => success on Next.js `16.1.6`
3. Task 5 blocker remediation:
   - `src/components/organisms/LocalAuthLogin.test.tsx` was aligned to current UI copy (`"Enter Mission Control"`), resolving stale selector failures.

## 2026-02-26 Rollout Update (Phase 16 Agent Uptime Autorecovery)

Phase 16 runtime was published and rolled to production with immutable SHA tags from commit `c4889c7`.

Verification snapshot:
1. Image publish workflow:
   - Workflow: `publish-mission-control-images.yml` (`workflow_dispatch`)
   - Run ID: `22452058574`
   - Conclusion: `success`
   - URL: `https://github.com/kr8tiv-ai/kr8tiv-mission-control/actions/runs/22452058574`
2. VPS rollout action:
   - Hostinger action ID: `81038315`
   - Action: `docker_compose_up`
   - State: `success`
   - Completed at: `2026-02-26T16:55:03Z`
3. Immutable runtime images now active:
   - Backend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:c4889c7`
   - Webhook worker: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:c4889c7`
   - Frontend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-frontend:c4889c7`
4. Public availability checks:
   - `http://76.13.106.100:8100/health` => `200`
   - `http://76.13.106.100:8100/readyz` => `200`
   - `http://76.13.106.100:3100` => `200`
5. Recovery API live checks:
   - `GET /api/v1/runtime/recovery/policy` => `200`
   - `GET /api/v1/runtime/recovery/incidents?board_id=b1000000-0000-0000-0000-000000000001&limit=5` => `200`
   - `POST /api/v1/runtime/recovery/run?board_id=b1000000-0000-0000-0000-000000000001` => `200`
6. Recovery run evidence:
   - Result summary: `total_incidents=2`, `recovered=2`, `failed=0`, `suppressed=0`
   - Incident reasons: `heartbeat_stale` with action `session_resync`
7. OpenAPI route presence confirmed:
   - `/api/v1/runtime/recovery/policy`
   - `/api/v1/runtime/recovery/incidents`
   - `/api/v1/runtime/recovery/run`
   - `/api/v1/boards/{board_id}/agent-continuity`

## 2026-02-26 Rollout Update (Post-Merge Main Re-Pin)

After PR `#3` merged to `main` at `8264dd1cef1a8edeb82c7401c5e174ffb195f66d`, runtime was re-pinned from branch tag `c4889c7` to main SHA tag `8264dd1` for GitHub/deploy parity.

Verification snapshot:
1. Main image publish workflow:
   - Workflow: `publish-mission-control-images.yml` (`push` on `main`)
   - Run ID: `22452397604`
   - Conclusion: `success`
   - URL: `https://github.com/kr8tiv-ai/kr8tiv-mission-control/actions/runs/22452397604`
2. VPS rollout action:
   - Hostinger action ID: `81039640`
   - Action: `docker_compose_up`
   - State: `success`
   - Completed at: `2026-02-26T17:03:51Z`
3. Active immutable images:
   - Backend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:8264dd1`
   - Webhook worker: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:8264dd1`
   - Frontend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-frontend:8264dd1`
4. Live endpoint checks:
   - `http://76.13.106.100:8100/health` => `200`
   - `http://76.13.106.100:8100/readyz` => `200`
   - `http://76.13.106.100:3100` => `200`
   - `GET /api/v1/runtime/recovery/policy` => `200`
   - `GET /api/v1/runtime/recovery/incidents?board_id=b1000000-0000-0000-0000-000000000001&limit=5` => `200`
   - `POST /api/v1/runtime/recovery/run?board_id=b1000000-0000-0000-0000-000000000001` => `200`

## 2026-02-26 Phase 17 Development Verification (Pre-Rollout)

Phase 17 scheduler + dedupe changes were validated in branch worktree before production deployment.

Verification snapshot:
1. Focused recovery suite:
   - `uv run pytest tests/test_recovery_models.py tests/test_recovery_engine.py tests/test_recovery_ops_api.py tests/test_recovery_alert_routing.py tests/test_recovery_scheduler.py tests/test_queue_worker_recovery_scheduler.py -q`
   - Result: `16 passed`
2. Policy/API extension validated:
   - `alert_dedupe_seconds` now present in model defaults and policy update/read API payloads.
3. Scheduler + dedupe service validated:
   - periodic sweep service executes board recovery and routes alerts.
   - duplicate incidents inside dedupe window suppress alert delivery.
4. Worker integration validated:
   - queue worker executes scheduler tick path when `recovery_loop_enabled=true`.
   - no-op behavior when `recovery_loop_enabled=false`.

Production rollout evidence will be appended after immutable image publish + VPS deploy.

## 2026-02-27 Rollout Update (Phase 19 Forced Resync + DB Hardening Live)

Phase 19 forced-recovery controls were merged and deployed with immutable images from commit `db352ac6e6e6001ab0604683ebf03afadc089265`.

Verification snapshot:
1. Main image publish workflow:
   - Workflow: `publish-mission-control-images.yml` (`push` on `main`)
   - Run ID: `22467489063`
   - Conclusion: `success`
   - URL: `https://github.com/kr8tiv-ai/kr8tiv-mission-control/actions/runs/22467489063`
2. VPS rollout action:
   - Hostinger action ID: `81083656`
   - Action: `docker_compose_up`
   - State: `success`
   - Completed at: `2026-02-27T00:40:23Z`
3. Active immutable images:
   - Backend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:db352ac`
   - Webhook worker: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:db352ac`
   - Frontend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-frontend:db352ac`
4. Runtime checks:
   - `http://76.13.106.100:8100/health` => `200`
   - `http://76.13.106.100:8100/readyz` => `200`
   - `http://76.13.106.100:3100` => `200`
   - Postgres exposure check: `76.13.106.100:5432` => `closed`
5. Forced-recovery behavior check:
   - `POST /api/v1/runtime/recovery/run?board_id=b1000000-0000-0000-0000-000000000001&force=true` => `200`
   - Result summary: `total_incidents=4`, `recovered=4`, `failed=0`, `suppressed=0`
   - Forced action count: `forced_heartbeat_resync=4`
6. Board agent state check:
   - `GET /api/v1/agents?board_id=b1000000-0000-0000-0000-000000000001` => all 4 board agents `online`
7. OpenClaw poller ownership hygiene:
   - Verified unique Telegram bot token per project (`openclaw-arsenal`, `openclaw-edith`, `openclaw-jocasta`, `openclaw-ydy8`)
   - Controlled restarts completed:
     - `81083825` (arsenal) success
     - `81083832` (edith) success
     - `81083840` (jocasta) success
     - `81083849` (ydy8) success

## 2026-02-27 Phase 19 Development Verification (Forced Heartbeat Resync)

Phase 19 manual recovery hardening was validated in local worktree before rollout.

Verification snapshot:
1. New force-run behavior tests:
   - `uv run pytest backend/tests/test_recovery_engine.py backend/tests/test_recovery_ops_api.py -q`
   - Result: `8 passed`
2. Recovery regression suite:
   - `uv run pytest backend/tests/test_recovery_models.py backend/tests/test_recovery_engine.py backend/tests/test_recovery_ops_api.py backend/tests/test_recovery_alert_routing.py backend/tests/test_recovery_scheduler.py backend/tests/test_queue_worker_recovery_scheduler.py -q`
   - Result: `19 passed`
3. Runtime behavior changes:
   - `POST /api/v1/runtime/recovery/run` now accepts `force=true`.
   - `force=true` bypasses cooldown suppression for that run.
   - `force=true` enables forced heartbeat resync for `heartbeat_stale` and `heartbeat_missing`, immediately marking matching board agents `online` with refreshed `last_seen_at`.

Production rollout evidence will be appended after immutable image publish + VPS deploy.

## 2026-02-26 Heartbeat Timeout Mitigation Update

Root-cause findings from live logs:
1. EDITH lane was still being patched with legacy locked model ID `google-gemini-cli/gemini-3.1`, which current runtime rejected (`FailoverError: Unknown model`).
2. This surfaced as repeated embedded-run failures during heartbeat cycles and looked like heartbeat instability.

Remediation implemented in backend:
1. Locked model policy canonical IDs updated:
   - EDITH -> `google-gemini-cli/gemini-3-pro-preview`
   - JOCASTA -> `nvidia/moonshotai/kimi-k2.5`
2. Legacy model aliases are now normalized automatically in model-policy parsing:
   - `google-gemini-cli/gemini-3.1` -> `google-gemini-cli/gemini-3-pro-preview`
   - `nvidia/moonshotai/kimi-k2-5` -> `nvidia/moonshotai/kimi-k2.5`
3. Locked-policy reconciliation now runs during heartbeat check-ins so stale DB rows self-correct over time without manual migration.

Verification:
1. `uv run pytest backend/tests/test_agent_model_policy.py -q` -> `5 passed`
2. `uv run pytest backend/tests/test_agent_provisioning_utils.py -q` -> `32 passed`
3. `uv run pytest backend/tests/test_task_mode_supermemory_callout.py backend/tests/test_task_mode_arena_config.py backend/tests/test_task_mode_schema.py -q` -> `9 passed`

## 2026-02-26 Incident Addendum (Telegram Heartbeat Timeout + Churn)

Live diagnosis against VPS `1302498` OpenClaw project logs found a repeating failure pattern:
1. Telegram poller conflicts:
   - `getUpdates ... 409: Conflict: terminated by other getUpdates request`
2. Long embedded run stalls during heartbeat cycles:
   - `embedded run timeout ... timeoutMs=600000`
3. Model/API saturation during heartbeat-driven runs:
   - `API rate limit reached. Please try again later.`
4. Repeated unused-channel health restarts:
   - `[health-monitor] [whatsapp:default] restarting (reason: stopped)` and hourly restart-cap skips.

Local hardening changes prepared for rollout:
1. Heartbeat cadence safety:
   - Default heartbeat changed from `15m` to `20m`.
   - `includeReasoning` default changed to `false` for lightweight liveness checks.
   - Aggressive intervals (below `15m`) are clamped to the safe default during provisioning sync.
2. Channel policy enforcement during heartbeat sync:
   - `channels.telegram.configWrites=false` and `channels.telegram.accounts.default.configWrites=false` enforced.
   - `whatsapp` channel is explicitly disabled when not enabled by `enabled_ingress_channels`.
3. HEARTBEAT template simplification:
   - Removes per-heartbeat OpenAPI fetch requirements.
   - Reduces pre-flight to lightweight check-in path.
   - Allows safe idle `HEARTBEAT_OK` no-op cycles instead of forced assist chatter.

Verification status:
1. Backend focused + full suite:
   - `424 passed, 1 xfailed`
2. Frontend suite + build:
   - `81 passed`
   - `next build` success

Live API mitigation attempt:
1. Attempted immediate PATCH of board agent heartbeat configs to `20m` via `/api/v1/agents/{id}`.
2. Response: `502 Bad Gateway` for all four board agents (provisioning path currently blocked by gateway connectivity/auth posture).
3. Required next action: deploy this hardening build, then run gateway template sync/reprovision so channel + heartbeat policies are pushed from Mission Control.

## 2026-02-26 Rollout Update (Phase 18 Migration Gate Live)

Phase 18 was merged to `main` and deployed to production with immutable images from commit `b9fa9039fdbab05b5c68cc8c6902261d5552b6de`.

Verification snapshot:
1. Main image publish workflow:
   - Workflow: `publish-mission-control-images.yml` (`push` on `main`)
   - Run ID: `22458967039`
   - Conclusion: `success`
   - URL: `https://github.com/kr8tiv-ai/kr8tiv-mission-control/actions/runs/22458967039`
2. VPS rollout action:
   - Hostinger action ID: `81059870`
   - Action: `docker_compose_up`
   - State: `success`
   - Completed at: `2026-02-26T20:07:24Z`
3. Active immutable images:
   - Backend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:b9fa903`
   - Webhook worker: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:b9fa903`
   - Frontend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-frontend:b9fa903`
4. Live endpoint checks:
   - `http://76.13.106.100:8100/health` => `200`
   - `http://76.13.106.100:8100/readyz` => `200`
   - `http://76.13.106.100:3100` => `200`
   - `http://76.13.106.100:48650/health` => `200`
   - `http://76.13.106.100:48651/health` => `200`
   - `http://76.13.106.100:48652/health` => `200`
   - `http://76.13.106.100:48653/health` => `200`
   - `GET /api/v1/runtime/recovery/policy` => `200`
   - `GET /api/v1/runtime/recovery/incidents?board_id=b1000000-0000-0000-0000-000000000001&limit=5` => `200`
   - `POST /api/v1/runtime/recovery/run?board_id=b1000000-0000-0000-0000-000000000001` => `200`
5. Scheduler startup gate evidence:
   - Worker log confirms migration gate readiness event:
     - `queue.worker.recovery_gate.ready ... head_revision=a8c1d2e3f4b5`
   - Recovery scheduler executes after gate:
     - `queue.worker.recovery_sweep ... board_count=1 incident_count=4 ...`
   - No transient recovery `UndefinedColumn` startup loop observed during this rollout.

## 2026-02-26 Rollout Update (Phase 17 Scheduler + Dedupe Live)

Phase 17 was merged to `main` and deployed to production with immutable images from merge commit `f8a4338f7701f61485db69e5b808a5a7f503a41f`.

Verification snapshot:
1. Main image publish workflow:
   - Workflow: `publish-mission-control-images.yml` (`push` on `main`)
   - Run ID: `22457484276`
   - Conclusion: `success`
   - URL: `https://github.com/kr8tiv-ai/kr8tiv-mission-control/actions/runs/22457484276`
2. VPS rollout action:
   - Hostinger action ID: `81054769`
   - Action: `docker_compose_up`
   - State: `success`
   - Completed at: `2026-02-26T19:24:13Z`
3. Active immutable images:
   - Backend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:f8a4338`
   - Webhook worker: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-backend:f8a4338`
   - Frontend: `ghcr.io/kr8tiv-ai/kr8tiv-mission-control-frontend:f8a4338`
4. Live endpoint checks:
   - `http://76.13.106.100:8100/health` => `200`
   - `http://76.13.106.100:8100/readyz` => `200`
   - `http://76.13.106.100:3100` => `200`
   - `GET /api/v1/runtime/recovery/policy` => `200` with `alert_dedupe_seconds=900`
   - `GET /api/v1/runtime/recovery/incidents?board_id=b1000000-0000-0000-0000-000000000001&limit=5` => `200`
   - `POST /api/v1/runtime/recovery/run?board_id=b1000000-0000-0000-0000-000000000001` => `200`
5. Scheduler runtime evidence:
   - Webhook worker log event observed:
     - `queue.worker.recovery_sweep ... board_count=1 incident_count=3 ...`
   - Confirms periodic scheduler path executed live.

Startup note:
- During first seconds of rollout, webhook worker emitted transient `UndefinedColumn` errors before backend startup migration completed.
- The loop recovered automatically after migration and proceeded with successful sweep execution.

## 2026-02-26 Phase 18 Development Verification (Pre-Rollout)

Phase 18 migration-gate changes were validated in branch worktree before production deployment.

Verification snapshot:
1. Migration gate unit suite:
   - `uv run pytest tests/test_recovery_migration_gate.py -q`
   - Result: `3 passed`
2. Queue worker scheduler gate integration:
   - `uv run pytest tests/test_queue_worker_recovery_scheduler.py -q`
   - Result: `3 passed`
   - Confirms scheduler no-ops when migrations are pending.
3. Focused recovery regression suite:
   - `uv run pytest tests/test_recovery_migration_gate.py tests/test_queue_worker_recovery_scheduler.py tests/test_recovery_scheduler.py tests/test_recovery_engine.py tests/test_recovery_ops_api.py -q`
   - Result: `15 passed`
4. Runtime behavior change:
   - `run_recovery_scheduler_once()` now gates scheduler execution on `is_scheduler_migration_ready()`.
   - Worker emits `queue.worker.recovery_sweep_deferred_migrations_pending` until DB revision reaches Alembic head.

Production rollout evidence will be appended after immutable image publish + VPS deploy.

## 2026-02-27 Runtime Hardening Update (WhatsApp Schema Compatibility + NotebookLM Planning Queries)

1. Channel patch compatibility fix:
   - Updated heartbeat provisioning patch logic to stop emitting unsupported top-level key:
     - removed `channels.whatsapp.enabled` patch writes
     - retained account-level disable patch:
       - `channels.whatsapp.accounts.default.enabled=false`
   - Rationale:
     - Some OpenClaw runtimes reject `channels.whatsapp.enabled` as an unknown key, which can invalidate patch attempts and re-introduce channel restart noise.
2. Test-first validation:
   - Updated `test_patch_agent_heartbeats_disables_whatsapp_when_not_enabled` to require account-level only disable.
   - Verification run:
     - `uv run pytest backend/tests/test_agent_provisioning_utils.py::test_patch_agent_heartbeats_disables_whatsapp_when_not_enabled -q` => `1 passed`
     - `uv run pytest backend/tests/test_agent_provisioning_utils.py -k "patch_agent_heartbeats" -q` => `5 passed`
3. NotebookLM phase-planning query sweep:
   - Notebook queried: `c276018f-768b-4c7b-a8a8-cd96110d990b`
   - Query artifact:
     - `docs/operations/2026-02-27-notebooklm-phase20-qna.md`
   - Topics queried:
     - reliability failure patterns
     - heartbeat/Telegram stabilization priorities
     - persona anti-drift controls
     - notebook capability-gate checks
     - rollout verification checklist
     - GSD telemetry metrics
4. GSD planning outputs produced from query synthesis:
   - `docs/plans/2026-02-27-phase20-22-heartbeat-capability-gate-design.md`
   - `docs/plans/2026-02-27-phase20-22-heartbeat-capability-gate-implementation.md`

## 2026-02-27 GSD Spec Continuation (Phase 20/21 Implementation Batch)

1. Heartbeat contract hardening:
   - Added template contract test:
     - `backend/tests/test_heartbeat_template_contract.py`
   - Updated heartbeat worker loop wording in `BOARD_HEARTBEAT.md.j2` to require successful pre-flight check-in before idle `HEARTBEAT_OK`.
2. NotebookLM capability gate service:
   - Added runtime gate:
     - `backend/app/services/notebooklm_capability_gate.py`
   - Added adapter probe helper:
     - `check_notebook_access()` in `backend/app/services/notebooklm_adapter.py`
   - Added gate test suite:
     - `backend/tests/test_notebooklm_capability_gate.py`
3. Notebook mode integration:
   - Enforced gate before NotebookLM operations in:
     - `backend/app/services/task_mode_execution.py`
     - `backend/app/api/tasks.py` (`POST /api/v1/tasks/{task_id}/notebook/query`)
   - Added task-mode gate tests:
     - `backend/tests/test_task_mode_notebook_capability_gate.py`
4. Verification:
   - `uv run pytest backend/tests/test_heartbeat_template_contract.py backend/tests/test_notebooklm_capability_gate.py backend/tests/test_task_mode_notebook_capability_gate.py backend/tests/test_task_mode_supermemory_callout.py backend/tests/test_task_mode_schema.py -q` => `16 passed`
   - `uv run pytest backend/tests/test_tasks_api_rows.py -q` => `5 passed`

## 2026-02-27 GSD Spec Continuation (Phase 22 Telemetry Metrics Batch)

1. Added `metrics_snapshot` support to GSD run telemetry:
   - Model: `backend/app/models/gsd_runs.py`
   - Schemas: `backend/app/schemas/gsd_runs.py`
   - API persistence/readback: `backend/app/api/gsd_runs.py`
2. Added migration for persisted environments:
   - `backend/migrations/versions/c1f8e4a6b9d2_add_gsd_run_metrics_snapshot.py`
3. Extended API tests:
   - `backend/tests/test_gsd_runs_api.py` now verifies create/update/read with metrics payload.
4. Verification:
   - `uv run pytest backend/tests/test_gsd_runs_api.py -q` => `2 passed`
   - Combined targeted regression:
     - `uv run pytest backend/tests/test_heartbeat_template_contract.py backend/tests/test_notebooklm_capability_gate.py backend/tests/test_task_mode_notebook_capability_gate.py backend/tests/test_task_mode_supermemory_callout.py backend/tests/test_task_mode_schema.py backend/tests/test_tasks_api_rows.py backend/tests/test_gsd_runs_api.py -q`
     - Result: `23 passed`
