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
