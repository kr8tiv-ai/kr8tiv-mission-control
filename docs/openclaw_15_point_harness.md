# OpenClaw 15-Point Runtime Harness

This harness is the operational acceptance checklist for a Mission Control + multi-agent OpenClaw deployment.

Use it after any restart, image update, config change, or credential rotation.

## Scope

- Mission Control stack health
- OpenClaw gateway reachability
- Agent model routing correctness
- Telegram delivery correctness
- Drift prevention (model lock + config write lock)
- Reboot persistence of enforcement

## Pre-Reqs

- SSH access to the host running Docker
- `kr8tiv-mission-control-backend-1` container up
- OpenClaw bot containers up
- `LOCAL_AUTH_TOKEN` present in backend container env

## 15 Checks

1. **All OpenClaw containers are healthy**
   - Expected: `openclaw-arsenal`, `openclaw-jocasta`, `openclaw-edith`, `openclaw-ydy8-openclaw-1` are `Up (...) (healthy)` or equivalent healthy state.

2. **Mission Control core containers are healthy**
   - Expected: backend, frontend, webhook-worker, db, redis are running.

3. **Gateway status endpoint is reachable**
   - Endpoint: `GET /api/v1/gateways/status?board_id=<board_id>`
   - Expected: `connected=true`.

4. **Lead lane model is codex**
   - Session key: `agent:lead-b1000000-0000-0000-0000-000000000001:main`
   - Expected: `modelProvider=openai-codex`, `model=gpt-5.3-codex`.

5. **Arsenal lane model is codex**
   - Session key: `agent:mc-c2000000-0000-0000-0000-000000000002:main`
   - Expected: `modelProvider=openai-codex`, `model=gpt-5.3-codex`.

6. **Jocasta lane model is kimi**
   - Session key: `agent:mc-c4000000-0000-0000-0000-000000000004:main`
   - Expected: `modelProvider=moonshotai`, `model=kimi-k2.5`.

7. **Edith lane model is Gemini**
   - Session key: `agent:mc-c3000000-0000-0000-0000-000000000003:main`
   - Expected: Gemini 3.1 family route is active for this lane.
   - If using `google-gemini-cli/*`: verify OAuth auth profile contains `token` + `projectId`.
   - If OAuth is unavailable: use `google/*` model route to remain operational.

8. **Per-bot config primary models are pinned**
   - Arsenal: `openai-codex/gpt-5.3-codex`
   - Friday: `openai-codex/gpt-5.3-codex`
   - Jocasta: `nvidia/moonshotai/kimi-k2-5`
   - Edith: chosen Gemini route (`google/*` or `google-gemini-cli/*`) matches your policy.
   - If Mission Control connects with a non-local Host header, set Friday gateway `controlUi.dangerouslyDisableDeviceAuth=true` (or use full device-identity auth).

9. **Locked policy enforcement**
   - Expected: `PATCH /api/v1/agents/{id}` rejects model-policy overrides for locked agents with `403`.

10. **Template sync enforcement**
   - Expected: `POST /api/v1/gateways/{gateway_id}/templates/sync` rewrites drifted model routes back to policy targets.

11. **Telegram bot tokens are present**
   - Expected: `channels.telegram.accounts.default.botToken` exists for each bot config.

12. **Telegram delivery test succeeds for each bot**
   - Send one probe message per bot token to an operator chat ID.
   - Expected: Telegram API returns `ok=true` for all probes.

13. **Runtime config writes are disabled**
   - Expected: `commands.config=false` in each OpenClaw config.

14. **Telegram config writes are disabled**
   - Expected: `channels.telegram.configWrites=false` and `channels.telegram.accounts.default.configWrites=false`.

15. **Enforcer timer is active, persistent, and reboot-safe**
   - Service: `openclaw-config-enforcer.timer`
   - Expected: `active (waiting)`, `Persistent=true`, `OnBootSec` and `OnUnitActiveSec` configured.

## Policy Overlay Checks (required for 2026 rollout)

- **Persona integrity baseline exists**
  - Expected: each active agent has checksum baseline row in `agent_persona_integrity`.
- **Persona precedence is present in rendered workspace docs**
  - Expected: `SOUL.md > USER.md > IDENTITY.md > AGENTS.md` appears in generated contract artifacts.
- **Reasoning default is max-capacity**
  - Expected: runtime config resolves `thinkingDefault=max` with fallback behavior `highest_or_model_default`.
- **Supermemory plugin bootstrap is enforced**
  - Expected bootstrap task includes `openclaw plugins install @supermemory/openclaw-supermemory`.
- **Install governance is ask-first by default**
  - Expected: installation requests default to `pending_owner_approval`.
- **Tier quota controls are active**
  - Expected: install requests over ability/storage limits are rejected with clear quota messages.
- **Backup reminder workflow is active**
  - Expected: unconfirmed tenants receive twice-weekly warning prompts and destination confirmation options.

## Additional Runtime Validation (recommended)

- Drift auto-revert works:
  Temporarily set one pinned model to an incorrect value, wait one enforcer interval, verify the route is auto-reverted.
- Recent logs show no critical routing/auth/delivery failures:
  Check last 15-20 minutes of all OpenClaw bot logs for recurring `chat not found`, `token missing`, `No available auth profile`, or provider cooldown loops.

## Phase 16 Recovery Validation Overlay

Run these checks after deploying any build that includes `recovery_ops` and `recovery_engine`:

1. Recovery policy endpoint works
   - `GET /api/v1/runtime/recovery/policy`
   - Expected: `200` with policy payload.
2. Incident listing endpoint works
   - `GET /api/v1/runtime/recovery/incidents?board_id=<board_id>&limit=5`
   - Expected: `200` with incident array payload.
3. Manual recovery run works
   - `POST /api/v1/runtime/recovery/run?board_id=<board_id>`
   - Expected: `200` with summary fields:
     - `total_incidents`
     - `recovered`
     - `failed`
     - `suppressed`
4. Recovery routes are visible in OpenAPI
   - `/api/v1/runtime/recovery/policy`
   - `/api/v1/runtime/recovery/incidents`
   - `/api/v1/runtime/recovery/run`
5. Immutable image pins reflect rollout commit
   - `backend` and `webhook-worker` share same backend SHA tag.
   - `frontend` has matching rollout SHA tag.

## Phase 17 Scheduler + Dedupe Validation Overlay

Run these checks after deploying a build that includes periodic scheduler ticks:

1. Recovery policy includes dedupe control
   - `GET /api/v1/runtime/recovery/policy`
   - Expected field: `alert_dedupe_seconds` (integer).
2. Worker scheduler loop is enabled
   - Verify runtime config resolves:
     - `recovery_loop_enabled=true`
     - `recovery_loop_interval_seconds` is a positive integer.
3. Scheduler sweep logs appear periodically
   - Expected structured log event: `queue.worker.recovery_sweep`.
4. Duplicate alerts are suppressed
   - Trigger same board/agent/status/reason incident twice inside dedupe window.
   - Expected: second event increments dedupe suppression and does not send owner alert.
5. Incident persistence remains complete
   - Expected: incidents are still persisted even when alert is deduped.

## Evidence Capture Template

Capture and store:

- `docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}'`
- Gateway status JSON snippet for lead/c200/c300/c400
- One Telegram probe response per bot (`ok=true`)
- Enforcer timer/service status output
- Drift-revert proof (before/after values)
- Tail of recent logs for each OpenClaw container

## Known Pitfall: Gemini CLI vs Gemini API

- `google-gemini-cli/*` uses Cloud Code Assist OAuth and fails with plain API key (`401` / `Invalid Google Cloud Code Assist credentials`).
- `google/*` uses API-key auth and is appropriate when only `GEMINI_API_KEY` is available.
- Decide this route explicitly in policy docs and enforce it in your config enforcer to avoid silent drift.
