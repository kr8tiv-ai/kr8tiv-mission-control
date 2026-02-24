# OpenClaw 15-Point Harness

Use this checklist after deploys, image upgrades, credential rotation, or config changes to confirm Mission Control and OpenClaw are still aligned.

## Preconditions

- Mission Control API is reachable.
- OpenClaw gateway URL and token are configured.
- Templates have been synced at least once for the target board.
- You can inspect container logs and current OpenClaw config state.

## 15 Verification Checks

1. **Container health**
   All Mission Control and OpenClaw containers are `Up` and healthy.

2. **Mission Control health endpoint**
   `GET /api/v1/health` returns `ok`.

3. **Gateway connectivity**
   `GET /api/v1/gateways/status?board_id=<board_id>` reports `connected=true`.

4. **Main agent availability**
   The gateway main agent exists (`board_id = null`) and responds.

5. **Friday model policy lock**
   Friday is locked to `openai-codex/gpt-5.3-codex`.

6. **Arsenal model policy lock**
   Arsenal is locked to `openai-codex/gpt-5.3-codex`.

7. **Edith model policy lock**
   Edith is locked to the configured Gemini route for your environment.

8. **Jocasta model policy lock**
   Jocasta is locked to `nvidia/moonshotai/kimi-k2-5`.

9. **Locked policy enforcement**
   `PATCH /api/v1/agents/{id}` rejects model-policy overrides for locked agents with `403`.

10. **Template sync enforcement**
    `POST /api/v1/gateways/{gateway_id}/templates/sync` rewrites drifted models back to policy targets.

11. **OpenClaw runtime model alignment**
    `config.get` shows `agents.list[].model` values matching locked policies.

12. **Config write hardening**
    Runtime config writes are disabled for bot-controlled channels in production.

13. **Telegram delivery check**
    One probe per configured bot token succeeds (`ok=true`).

14. **Restart persistence**
    After restart, gateway reconnects and locked model assignments remain unchanged.

15. **Log sanity**
    Last 15-20 minutes of logs show no repeated auth/routing/delivery failure loops.

## Evidence Capture

Capture these artifacts for each validation run:

- `docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}'`
- Gateway status payloads for relevant board and main agent paths
- Locked agent policy snapshot (before and after template sync)
- Telegram probe responses
- Tail logs for each OpenClaw container

## Gemini Route Note

- `google-gemini-cli/*` requires OAuth profile auth.
- `google/*` is API-key based.
- Pick one route intentionally in policy docs and keep the enforcer aligned to prevent silent drift.
