# TASKS

## Tenant Provisioning
- [ ] Create tenant workspace and state volumes for `tenant-acme`.
- [ ] Set `OPENCLAW_GATEWAY_TOKEN` in secret manager / secret file.
- [ ] Set Mission Control token file at `/run/secrets/mission_control_token`.
- [ ] Generate workspace artifacts from harness.

## Security Baseline
- [ ] Confirm DM pairing: enabled.
- [ ] Confirm mention gating: enabled.
- [ ] Review tool allow/deny lists before go-live.
- [ ] Verify non-main session sandboxing is enabled.

## Messaging Channels
- [ ] Configure WhatsApp integration (enabled in harness).
- [ ] Configure Telegram integration (enabled in harness).
- [ ] Ensure token injection uses runtime secret files, not committed env values.

## Model Policy
- [ ] Enforce primary model: openai-codex/gpt-5.3-codex
- [ ] Confirm fallback list: openai-codex/gpt-5-codex
- [ ] Confirm runtime overrides are blocked: true
- [ ] Validate fallback triggers: rate_limit, provider_cooldown

## Control Plane Policy
- [ ] Confirm Mission Control URL: http://mission-control:8000
- [ ] Confirm tier: enterprise
- [ ] Confirm pack ref: engineering-delivery-pack@2
- [ ] Confirm telemetry enabled: true
- [ ] Confirm privacy flags: tenant=false, user=false

## Recovery Policy
- [ ] Confirm recovery order: FRIDAY -> ARSENAL -> JOCASTA -> EDITH
- [ ] Confirm single-owner recovery mode: true
- [ ] Confirm recovery cooldown seconds: 420

## Supermemory
- [ ] Create scoped API key per tenant.
- [ ] Validate containerTag: tenant-acme.
- [ ] Validate ingestion + retrieval smoke test.

## Operations
- [ ] Deploy compose stack and confirm healthcheck passes.
- [ ] Configure watchdog webhook (enabled).
- [ ] Verify runtime can resolve champion pack via Mission Control.
- [ ] Verify runtime telemetry reaches Mission Control for each run.
- [ ] Add monitor alerting for 5+ minute downtime.
- [ ] Verify backup policy for tenant state/workspace volumes.

## Upstream Update Procedure
- [ ] Track OpenClaw stable ring updates.
- [ ] Regenerate artifacts on update.
- [ ] Re-run golden tests before rollout.
