# OpenClaw 15-Point Harness

Use this harness after deployment to verify Mission Control + OpenClaw behavior end to end.

## Preconditions

- Mission Control backend is reachable.
- Gateway URL/token are configured in Mission Control.
- Agent templates have been synced at least once.

## Harness Steps

1. Gateway health check: `openclaw health` returns healthy.
2. Mission Control health check: `GET /api/v1/health` returns `ok`.
3. Gateway is registered in Mission Control with correct `workspace_root`.
4. Main gateway agent exists (`board_id = null`) and is online.
5. Friday agent exists and has `model_policy.model=openai-codex/gpt-5.3-codex`.
6. Arsenal agent exists and has `model_policy.model=openai-codex/gpt-5.3-codex`.
7. Edith agent exists and has `model_policy.model=google-gemini-cli/gemini-3.1`.
8. Jocasta agent exists and has `model_policy.model=nvidia/moonshotai/kimi-k2-5`.
9. Friday/Arsenal/Edith policies report `transport=cli` and `locked=true`.
10. Jocasta policy reports `transport=api` and `locked=true`.
11. `POST /api/v1/gateways/{gateway_id}/templates/sync` completes without fatal errors.
12. OpenClaw `config.get` shows each locked agent under `agents.list` with the expected `model`.
13. Attempting to patch a locked agent `model_policy` via `PATCH /api/v1/agents/{id}` returns `403`.
14. Restart gateway/container, then run template sync; locked model assignments remain unchanged.
15. Send one routed task per agent class (lead, worker, main) and confirm responses arrive through Mission Control pathways.

## Expected Outcome

All 15 checks pass. Any failure is a blocker for production rollout.
