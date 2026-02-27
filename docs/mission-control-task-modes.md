# Mission Control Task Modes

This page keeps deep operational details for Mission Control task-mode execution.

## Supported Task Modes

- `standard`
- `notebook`
- `arena`
- `arena_notebook`
- `notebook_creation`

## Backend Data Model

Task-mode support adds the following task fields:

- `task_mode`
- `arena_config` (JSONB)
- `notebook_profile`
- `notebook_id`
- `notebook_share_url`
- `notebook_gate_state` (`ready|retryable|misconfig|hard_fail|unknown`)
- `notebook_gate_reason`
- `notebook_gate_checked_at`

Arena rounds are persisted in `task_iterations`.

## NotebookLM Integration

NotebookLM integration is executed through the configured CLI runner.

- Default runner: `uvx --from notebooklm-mcp-cli@latest nlm`
- Profiles:
  - `enterprise`
  - `personal`
  - `auto` (tries personal, then enterprise)
- Persistent profile root:
  - `NOTEBOOKLM_PROFILES_ROOT=/var/lib/notebooklm/profiles`

Initial profile login examples:

```bash
uvx --from notebooklm-mcp-cli@latest nlm login --profile personal
uvx --from notebooklm-mcp-cli@latest nlm login --profile enterprise
```

Verification:

```bash
uvx --from notebooklm-mcp-cli@latest nlm notebook list --profile personal
```

## OpenClaw Security Baseline

- Mission Control should enforce `GATEWAY_MIN_VERSION=2026.2.26` or newer.
- This baseline aligns with upstream OpenClaw security fixes shipped in `v2026.2.26`.
- If a gateway reports older runtime metadata, Mission Control should treat it as incompatible and block control-plane operations until upgraded.

## Arena Execution Model

Arena execution is worker-driven and persists each reviewer iteration.

Inputs:

- agent list (up to 4 allowlisted agents)
- round count (`1..10`)
- final agent
- `supermemory_enabled`

Reviewer policy:

- reviewer defaults to `arsenal` (configurable via `ARENA_REVIEWER_AGENT`)
- reviewer is auto-injected for arena modes if omitted

Reviewer verdict protocol:

- `VERDICT: APPROVED`
- `VERDICT: REVISE`

If a valid verdict is missing, execution is marked as `ERROR` and fails safely.

Round cap behavior:

- if no `APPROVED` verdict appears before cap, final synthesis still runs with warning context

## Supermemory Arena Callout

Arena mode now uses the backend Supermemory adapter when `arena_config.supermemory_enabled=true`.

- bounded retrieval (`top_k`, thresholded hybrid search)
- tenant/container scoping via configured tag prefix
- graceful degradation:
  - missing API key
  - transport/API failures
  - malformed payloads
- on failure, execution continues without retrieval context

## UI Task-Mode Surfaces

Task create/update surfaces include:

- mode selector tabs
- arena agent multi-select
- round slider
- final agent selection
- Supermemory toggle
- notebook profile selector
- notebook source URL/text inputs (for notebook creation)

Task detail includes:

- task-mode metadata
- notebook query panel for notebook-capable modes
- arena iteration list with verdict display

## API Surface

Existing endpoint extended:

- `POST /api/v1/boards/{board_id}/tasks`

Task-mode endpoints:

- `GET /api/v1/boards/{board_id}/tasks/{task_id}/iterations`
- `POST /api/v1/boards/{board_id}/tasks/{task_id}/notebook/query`
- `GET /api/v1/runtime/notebook/gate`
- `GET /api/v1/runtime/notebook/gate-summary?board_id=<uuid>`
- `GET /api/v1/gsd-runs/{run_id}/summary`
- `POST /api/v1/runtime/verification/execute`
- `GET /api/v1/runtime/ops/control-plane-status?board_id=<uuid>&profile=auto`

## Phase 23-25 Control-Plane Additions

1. Notebook capability gate outcomes are now persisted on task rows for notebook-enabled modes.
2. Board operators can fetch notebook gate rollups through `gate-summary` for quick triage.
3. GSD telemetry now exposes previous-iteration deltas for continuity metrics.
4. Runtime verification harness can optionally attach evidence and block a GSD run when required checks fail.
5. Runtime verification harness now supports optional external URL probes:
   - Configure `VERIFICATION_EXTERNAL_HEALTH_URLS` with comma-separated URLs.
   - If configured, `external_health_probe` is required for harness pass.
   - If not configured, it is emitted as `skipped:unconfigured` and does not block.

## Operator Command Surface

Unified runtime status can be fetched via API or CLI:

```bash
# API
curl -H "Authorization: Bearer <LOCAL_AUTH_TOKEN>" \
  "http://localhost:8100/api/v1/runtime/ops/control-plane-status?board_id=<board_id>&profile=auto"

# CLI
python -m app.cli.control_plane_status \
  --base-url "http://localhost:8100" \
  --token "<LOCAL_AUTH_TOKEN>" \
  --board-id "<board_id>" \
  --profile auto
```

Verification gate config example:

```bash
export VERIFICATION_EXTERNAL_HEALTH_URLS="http://localhost:8100/health,http://localhost:8100/readyz"
curl -X POST -H "Authorization: Bearer <LOCAL_AUTH_TOKEN>" \
  "http://localhost:8100/api/v1/runtime/verification/execute?profile=auto"
```

## Worker Runtime

Queue worker entrypoint:

- `python -m app.services.queue_worker`

This processes:

- webhook deliveries
- task-mode orchestration jobs

## Operations and Troubleshooting

Common checks:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f webhook-worker
```

Frequent failure causes:

1. NotebookLM runner/profile issues:
   - runner command mismatch
   - missing profile login
   - profile root not mounted
2. Arena execution does not progress:
   - worker container offline
   - Redis connectivity problems
3. Tasks return to inbox:
   - safe fallback after orchestration error
   - inspect task comments for `[Task Mode Error]`

## Validation Commands

```bash
python -m pytest backend/tests/test_task_mode_schema.py -q
python -m pytest backend/tests/test_task_mode_arena_config.py -q
python -m pytest backend/tests/test_task_mode_verdict.py -q
python -m pytest backend/tests/test_task_mode_supermemory_callout.py -q
```
