# Kr8tiv Mission Control

[![CI](https://github.com/abhi1693/openclaw-mission-control/actions/workflows/ci.yml/badge.svg)](https://github.com/abhi1693/openclaw-mission-control/actions/workflows/ci.yml)

## Fork Attribution

- Upstream project: [OpenClaw Mission Control](https://github.com/abhi1693/openclaw-mission-control)
- Upstream owner: [@abhi1693](https://github.com/abhi1693)
- Fork owner and publishing organization: [kr8tiv-ai](https://github.com/orgs/kr8tiv-ai)

This distribution preserves upstream credit and keeps the upstream MIT license terms.

Kr8tiv Mission Control is a production-ready fork direction for OpenClaw Mission Control with mode-aware task orchestration:

- Standard task flow
- NotebookLM-grounded task flow
- Arena iterative multi-agent flow
- Arena + NotebookLM combined flow
- NotebookLM creation flow

It keeps the existing backend/frontend stack and auth model while adding durable multi-round execution and notebook integration.

## Architecture

### Core stack

- Frontend: Next.js + TypeScript (`frontend/`)
- Backend: FastAPI + SQLModel + Alembic (`backend/`)
- Queue: Redis + custom queue worker (`backend/app/services/queue_worker.py`)
- Database: PostgreSQL
- Runtime: Docker Compose (`compose.yml`)

### Task mode expansion

Tasks support:

- `standard`
- `notebook`
- `arena`
- `arena_notebook`
- `notebook_creation`

New task columns:

- `task_mode`
- `arena_config` (JSONB)
- `notebook_profile`
- `notebook_id`
- `notebook_share_url`

New table:

- `task_iterations` for round-by-round arena persistence

## Control-Plane Charter

Mission Control is the source of truth for how the fleet improves over time.

This fork is intentionally optimized for fast iteration, but it separates speed from chaos:

- OpenClaw harnesses execute work
- Mission Control governs prompt/context versions, evals, promotion, and rollback
- Agents can suggest changes, but only Mission Control can approve and deploy them

This keeps high-agency behavior and personality while preventing uncontrolled drift across teams.

### Scope model

- `global -> domain -> tenant -> user`
- Domain packs are reusable deployables (HR, legal, infrastructure, engineering, personal workflows)
- Tenant and user adaptation stay isolated by default

### Direction docs

- [`docs/production/AUTO_IMPROVE_CONTROL_PLANE.md`](docs/production/AUTO_IMPROVE_CONTROL_PLANE.md)
- [`docs/openclaw_15_point_harness.md`](docs/openclaw_15_point_harness.md)
- [`docs/openclaw_baseline_config.md`](docs/openclaw_baseline_config.md)

## Quick Start

### Prerequisites

- Docker Engine + Compose v2
- Git
- A valid `LOCAL_AUTH_TOKEN` if using local auth

### 1) Configure environment

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Set at minimum:

- `AUTH_MODE=local`
- `LOCAL_AUTH_TOKEN=<50+ character token>`
- `NEXT_PUBLIC_API_URL=http://localhost:8000`

Optional task-mode variables:

- `ARENA_ALLOWED_AGENTS=friday,arsenal,edith,jocasta`
- `ARENA_REVIEWER_AGENT=arsenal`
- `NOTEBOOKLM_RUNNER_CMD=uvx --from notebooklm-mcp-cli nlm`
- `NOTEBOOKLM_PROFILES_ROOT=/var/lib/notebooklm/profiles`
- `NOTEBOOKLM_TIMEOUT_SECONDS=120`

### 2) Start services

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

Endpoints:

- UI: `http://localhost:3000`
- API: `http://localhost:8000`
- Health: `http://localhost:8000/healthz`

### 3) Stop services

```bash
docker compose -f compose.yml --env-file .env down
```

## Migrations

Migrations run automatically in dev when enabled by config.

Manual:

```bash
cd backend
alembic upgrade head
```

Added migration for this expansion:

- `backend/migrations/versions/c7f4d1b2a9e3_add_task_modes_and_iterations.py`

## NotebookLM Integration

This fork uses `notebooklm-mcp-cli` through `uvx` at runtime.

### Profile model

- `enterprise`
- `personal`
- `auto` (tries `personal` then `enterprise`)

### Persistent auth storage

Compose mounts a shared named volume:

- `notebooklm_profiles:/var/lib/notebooklm/profiles`

This keeps NotebookLM profile cookies across container restarts.

### Initial profile login

Run profile login in backend/worker-compatible environment where `nlm` is available:

```bash
uvx --from notebooklm-mcp-cli nlm login --profile personal
uvx --from notebooklm-mcp-cli nlm login --profile enterprise
```

Then verify:

```bash
uvx --from notebooklm-mcp-cli nlm notebook list --profile personal
```

## Arena Execution Model

Arena modes are worker-driven and persisted.

### Inputs

- Agent list (up to 4 from allowlist)
- Rounds (`1..10`)
- Final agent
- Supermemory toggle

### Reviewer policy

- Fixed reviewer agent: `arsenal` (configurable with `ARENA_REVIEWER_AGENT`)
- Auto-injected if not selected by user

### VERDICT protocol

Reviewer output must include:

- `VERDICT: APPROVED`
- `VERDICT: REVISE`

If no valid verdict is found, execution records an `ERROR` verdict and task execution fails safely.

### Cap behavior

If no `APPROVED` before round cap, workflow finalizes with warning metadata and still runs the final agent.

## UI Changes

Task creation now includes mode tabs:

- Standard
- Notebook Task
- Arena
- Arena+Notebook
- Create NotebookLM

Additional form controls:

- Arena agent multi-select
- Arena rounds slider (1-10)
- Final agent select
- Supermemory toggle
- Notebook profile selector
- Notebook source URL/text inputs (for notebook creation mode)

Task detail panel now includes:

- Mode metadata
- Notebook query UI (for notebook-enabled modes)
- Arena iteration list with verdict badges

## API Surface

Existing endpoint extended:

- `POST /api/v1/boards/{board_id}/tasks`

New task-scoped endpoints:

- `GET /api/v1/boards/{board_id}/tasks/{task_id}/iterations`
- `POST /api/v1/boards/{board_id}/tasks/{task_id}/notebook/query`

## Worker Runtime

The compose worker now runs unified Python queue worker entrypoint:

- `python -m app.services.queue_worker`

This handles:

- Webhook deliveries
- Task mode orchestration jobs

## Operational Playbook

### Common issues

1. Notebook command failures:
   - Check `NOTEBOOKLM_RUNNER_CMD`
   - Verify profile login state
   - Verify profile volume mount
2. Arena task not progressing:
   - Ensure worker container is running
   - Check Redis connectivity and `RQ_REDIS_URL`
3. Tasks return to inbox:
   - Mode execution failed by design-safe fallback
   - Inspect task comments for `[Task Mode Error]`

### Useful checks

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f webhook-worker
```

## Testing

Backend examples:

```bash
python -m pytest backend/tests/test_task_mode_schema.py -q
python -m pytest backend/tests/test_task_mode_arena_config.py -q
python -m pytest backend/tests/test_task_mode_verdict.py -q
```

Frontend:

```bash
npm --prefix frontend run lint
```

## Open Source Fork Workflow

If publishing as a new public repository:

1. Create target repository in the `kr8tiv-ai` organization (for example `kr8tiv-mission-control`)
2. Add new remote:

```bash
git remote add kr8tiv <new-repo-url>
```

3. Push branch:

```bash
git push -u kr8tiv <branch-name>
```

4. Open PR from feature branch to your default branch

## License

MIT. See `LICENSE` and attribution details in `NOTICE`.
