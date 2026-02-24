# Kr8tiv Mission Control

Kr8tiv Mission Control is a downstream distribution of OpenClaw Mission Control focused on safe, repeatable tenant delivery at scale.

This repository now includes:

- upstream-compatible Mission Control backend/frontend runtime
- locked model-policy + harness-safe provisioning controls
- a TypeScript `kr8tiv-claw` distribution compiler
- an org-admin API for generating tenant bundles and downloading artifacts
- bounded Supermemory arena context retrieval with graceful fallback

[![CI](https://github.com/kr8tiv-ai/kr8tiv-mission-control/actions/workflows/ci.yml/badge.svg)](https://github.com/kr8tiv-ai/kr8tiv-mission-control/actions/workflows/ci.yml)

## Fork Attribution

- Upstream project: [OpenClaw Mission Control](https://github.com/abhi1693/openclaw-mission-control)
- Upstream owner: [@abhi1693](https://github.com/abhi1693)
- Fork owner: [kr8tiv-ai](https://github.com/orgs/kr8tiv-ai)
- License: MIT (`LICENSE`, `NOTICE`)

## Why This Architecture

Kr8tiv Mission Control is a production-ready fork direction for OpenClaw Mission Control with mode-aware task orchestration and a central prompt/context governance direction. The distribution layer is intentionally thin and plugin/template-oriented:

1. Keep divergence from upstream OpenClaw low.
2. Put tenant customization in generated workspace/config/compose artifacts.
3. Avoid adding mandatory infrastructure (no required Postgres/Redis/Kafka beyond existing stack).
4. Allow controlled adoption of upstream updates and selected fork patterns without deep core rewrites.

## Auto-Improvement Gate (New Direction)

We are implementing Mission Control as the mandatory quality gate for both market segments:

- **Individuals**: single-agent or small-agent deployments still route through Mission Control
- **Enterprise**: centralized governance across many agents/workspaces with scoped inheritance

This allows iterative prompt/context improvement for any model provider while keeping tenant privacy boundaries and rollback safety.

- Design document: [`docs/prompt-evolution-gate.md`](docs/prompt-evolution-gate.md)

## Architecture Overview

### Runtime Plane (Mission Control)

- FastAPI backend with SQLModel + Alembic
- Next.js frontend
- Redis-backed queue worker
- OpenClaw gateway orchestration and template sync
- Arena/notebook task modes

### Distribution Plane (`kr8tiv-claw`)

Top-level package: `kr8tiv-claw/`

Commands:

- `compile --harness <path> --out <dir> --tenant <slug>`
- `compose --harness <path> --out <dir> --tenant <slug> [--watchdog]`
- `health --token <OPENCLAW_GATEWAY_TOKEN>`

Compiler output:

- workspace files:
  - `AGENTS.md`
  - `SOUL.md`
  - `TOOLS.md`
  - `USER.md`
  - `HEARTBEAT.md`
  - optional `MEMORY.md`
- `openclaw.json` secure defaults
- `skill-pack-manifest.json` for `<workspace>/skills`
- `docker-compose.tenant.yml` (compose command)

### Supermemory Plane

- scoped container tags per tenant bundle
- hybrid retrieval with threshold + bounded results
- best-effort adapter semantics:
  - no hard runtime failure on API/network issues
  - warning logs + arena execution continues

## Repository Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── distribution.py
│   │   ├── schemas/
│   │   │   └── distribution.py
│   │   ├── services/
│   │   │   ├── distribution_service.py
│   │   │   ├── supermemory_adapter.py
│   │   │   └── task_mode_execution.py
│   ├── migrations/
│   └── tests/
├── kr8tiv-claw/
│   ├── src/
│   └── test/
└── docs/
```

## Required Bootstrap Step

This workflow treats the GSD bootstrap as required before implementation sessions:

```bash
npx get-shit-done-cc@latest
```

## Quick Start

### 1) Configure Environment

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Set at minimum:

- `AUTH_MODE=local`
- `LOCAL_AUTH_TOKEN=<50+ chars>`
- `NEXT_PUBLIC_API_URL=http://localhost:8000`

### 2) Start Stack

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

Endpoints:

- UI: `http://localhost:3000`
- API: `http://localhost:8000`
- Health: `http://localhost:8000/healthz`

### 3) Stop Stack

```bash
docker compose -f compose.yml --env-file .env down
```

## Generating a Tenant Instance

### Option A: CLI (Local Generation)

1. Build the distribution package:

```bash
cd kr8tiv-claw
npm install
npm run build
```

2. Run compiler:

```bash
node dist/index.js compile \
  --harness ./examples/harness.yaml \
  --out ../artifacts/tenants/acme-support-local \
  --tenant acme-support
```

3. Generate compose template:

```bash
node dist/index.js compose \
  --harness ./examples/harness.yaml \
  --out ../artifacts/tenants/acme-support-local \
  --tenant acme-support-local-1234abcd \
  --watchdog
```

### Option B: API (Org-Admin Managed)

1. Generate:

`POST /api/v1/distribution/generate`

```json
{
  "tenant_slug": "acme-support",
  "harness_yaml": "tenant:\n  slug: acme-support\n...",
  "include_watchdog": true
}
```

2. Inspect metadata:

`GET /api/v1/distribution/artifacts/{tenant_id}`

3. Download archive:

`GET /api/v1/distribution/artifacts/{tenant_id}/download`

Artifacts are stored under:

- `backend/artifacts/tenants/<tenant_slug>-<8hex>/`

## Secure Defaults and Safety Posture

Generated `openclaw.json` enforces:

- pairing required by default
- group mention-gating enabled
- strict sandbox for non-main sessions
- explicit tool allow/deny lists

Operational safety constraints:

- no new mandatory infrastructure introduced by distribution features
- Supermemory retrieval is optional and failure-tolerant
- tenant artifact IDs are collision-safe (`slug + 8hex`)
- artifact path traversal is rejected by service-level validation

## Docker Compose Template Behavior

Generated `docker-compose.tenant.yml` includes:

- OpenClaw gateway service
- per-tenant persistent volumes
- required healthcheck command:
  - `node dist/index.js health --token $OPENCLAW_GATEWAY_TOKEN`
- optional `agent-watchdog` sidecar (enabled via `--watchdog`)

Watchdog sidecar behavior:

- emits heartbeat pings to:
  - `OWNER_WEBHOOK_URL`
  - `MANAGEMENT_WEBHOOK_URL`
- interval configurable from harness observability settings

## Supermemory Integration Notes

Backend arena mode integration:

- gated by `arena_config.supermemory_enabled`
- retrieves compact context lines from `/v4/search` hybrid mode
- context prepended to arena summary prompt when available
- warnings logged when unavailable, without failing task execution

Relevant settings:

- `SUPERMEMORY_API_KEY`
- `SUPERMEMORY_BASE_URL`
- `SUPERMEMORY_TOP_K`
- `SUPERMEMORY_THRESHOLD`
- `SUPERMEMORY_TIMEOUT_SECONDS`
- `SUPERMEMORY_CONTAINER_TAG_PREFIX`

## Upstream-Safe Update Strategy

To keep long-term repo health:

1. Sync `origin/main` first.
2. Merge/fix incoming PR changes on top of latest main.
3. Keep distribution logic in:
   - `kr8tiv-claw/`
   - backend service/router/schema adapters
4. Avoid deep edits to core OpenClaw runtime behavior unless strictly required.
5. Re-run regression suite after each merge batch.

Recommended flow:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git checkout -b feat/<topic>
```

## Docker Desktop + MCP Notes

For local operator workflows:

- run Docker Desktop with compose v2 enabled
- ensure backend can execute configured distribution CLI command
- keep MCP/tooling optional and out of hard runtime dependencies
- prefer API-driven generation for org-admin audited flows

## Task Modes Deep Reference

Task-mode detailed docs moved to:

- `docs/mission-control-task-modes.md`

Additional docs:

- `docs/openclaw_15_point_harness.md`
- `docs/openclaw_baseline_config.md`
- `docs/openclaw_gateway_ws.md`
- `docs/security/2026-02-23-security-audit.md`

## Verification Commands

### Distribution package

```bash
cd kr8tiv-claw
npm test
npm run build
```

### Backend targeted gates

```bash
python -m pytest \
  backend/tests/test_agent_model_policy.py \
  backend/tests/test_agent_provisioning_utils.py \
  backend/tests/test_task_mode_schema.py \
  backend/tests/test_task_mode_verdict.py \
  backend/tests/test_task_mode_arena_config.py \
  backend/tests/test_supermemory_adapter.py \
  backend/tests/test_task_mode_supermemory_callout.py \
  backend/tests/test_distribution_service.py \
  backend/tests/test_distribution_api.py -q
```

Migration graph:

```bash
cd backend
python scripts/check_migration_graph.py
```

## Runbook: Health and Alerting

### Healthcheck fails in tenant compose

1. Confirm token is present:
   - `OPENCLAW_GATEWAY_TOKEN`
2. Run health manually:
   - `node dist/index.js health --token <token>`
3. Validate generated `openclaw.json` parses correctly.

### Watchdog alerts not firing

1. Verify `OWNER_WEBHOOK_URL` and `MANAGEMENT_WEBHOOK_URL` are set.
2. Confirm `agent-watchdog` service is running.
3. Check sidecar logs for outbound POST failures.

### Distribution API generation fails

1. Verify `DISTRIBUTION_CLI_COMMAND` points to built `kr8tiv-claw` entrypoint.
2. Confirm `kr8tiv-claw` dependencies are installed and built.
3. Inspect backend logs for subprocess stderr detail.

## License

MIT.
