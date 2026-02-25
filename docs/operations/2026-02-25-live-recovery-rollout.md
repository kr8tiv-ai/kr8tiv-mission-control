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

