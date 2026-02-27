# Runtime Image Policy

## Objective

Production deploys must be reproducible and restart-safe. Mission Control runtime services must run from immutable, pullable image tags.

## Rules

1. Never deploy production with local-only image names.
2. Never rely on floating tags (`latest`, `main`) for production rollout.
3. Backend and frontend images must be tagged with:
   - git SHA
   - UTC timestamp
4. Rollout compose must pin exact image tags for:
   - `backend`
   - `webhook-worker` (same backend image)
   - `frontend`

## Tag Format

1. Backend:
   - `ghcr.io/<owner>/<repo>:kr8tiv-mc-backend-<sha>-<utc>`
2. Frontend:
   - `ghcr.io/<owner>/<repo>:kr8tiv-mc-frontend-<sha>-<utc>`

## Release Flow

1. Build backend image from repo root using `backend/Dockerfile`.
2. Build frontend image from `frontend/` using `frontend/Dockerfile`.
3. Push both tags to GHCR.
4. Update runtime compose to exact published tags.
5. Deploy and verify:
   - `/health` => `200`
   - frontend root => `200`
   - control-plane OpenAPI routes present

## Verification Gates

1. `docker pull <backend_tag>` succeeds from target host.
2. `docker pull <frontend_tag>` succeeds from target host.
3. `docker compose ps` shows all services on expected tags.
4. Mission Control API and board/task endpoints return expected status with auth.
5. CI runtime rollout health gate passes (or is explicitly `skipped` when URLs are unconfigured):
   - Script: `scripts/ci/rollout_health_gate.py`
   - Inputs:
     - `RUNTIME_HEALTH_URLS` (comma-separated)
     - `RUNTIME_ROLLBACK_COMMAND` (optional)
   - Evidence artifacts:
     - `artifacts/rollout/health-gate.json`
     - `artifacts/rollout/health-gate.env`
6. Skip policy:
   - `push` on `main`: `skipped` is treated as failure (`--fail-on-skipped` enforced).
   - `workflow_dispatch`: operator may set `allow_skipped_gate=true` for non-prod/debug runs.
7. Main preflight:
   - `publish-mission-control-images.yml` now fails early on `main` when `RUNTIME_HEALTH_URLS` is unset.
   - This prevents wasted image build/push cycles on non-validated rollout attempts.
8. Gate-only dispatch mode:
   - `workflow_dispatch` input `gate_only=true` runs rollout validation without image build/push.
   - Use this mode to validate `RUNTIME_HEALTH_URLS` and rollback wiring quickly.

## Rollback

1. Keep previous known-good backend + frontend tags.
2. Roll back by pinning previous tags in compose.
3. Re-run `docker compose up -d`.
4. For automated rollback in CI, configure:
   - `RUNTIME_HEALTH_URLS` to required runtime probes
   - `RUNTIME_ROLLBACK_COMMAND` to an operator-approved rollback command
5. Rollout gate semantics:
   - `passed`: rollout healthy
   - `failed`: rollout unhealthy (and rollback attempted if configured)
   - `skipped`: gate intentionally bypassed due missing URL configuration (not allowed on `main`)
6. Gate evidence now includes `status_reason`:
   - `no_urls_configured`
   - `all_probes_healthy`
   - `probe_failures`
