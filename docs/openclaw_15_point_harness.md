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
   - Jocasta: `nvidia/moonshotai/kimi-k2.5`
   - Edith: chosen Gemini route (`google/*` or `google-gemini-cli/*`) matches your policy.
   - If Mission Control connects with a non-local Host header, set Friday gateway `controlUi.dangerouslyDisableDeviceAuth=true` (or use full device-identity auth).

9. **Telegram bot tokens are present**
   - Expected: `channels.telegram.accounts.default.botToken` exists for each bot config.

10. **Telegram delivery test succeeds for each bot**
    - Send one probe message per bot token to an operator chat ID.
    - Expected: Telegram API returns `ok=true` for all probes.

11. **Runtime config writes are disabled**
    - Expected: `commands.config=false` in each OpenClaw config.

12. **Telegram config writes are disabled**
    - Expected: `channels.telegram.configWrites=false` and `channels.telegram.accounts.default.configWrites=false`.

13. **Enforcer timer is active and persistent**
    - Service: `openclaw-config-enforcer.timer`
    - Expected: `active (waiting)`, `Persistent=true`, `OnBootSec` and `OnUnitActiveSec` configured.

14. **Drift auto-revert works**
    - Temporarily set one pinned model to an incorrect value.
    - Wait one enforcer interval.
    - Expected: value reverts to pinned model automatically.

15. **Recent logs show no critical routing/auth/delivery failures**
    - Check last 15-20 minutes of all OpenClaw bot logs.
    - Expected: no recurring `chat not found`, `token missing`, `No available auth profile`, or provider cooldown loops for active lanes.

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
