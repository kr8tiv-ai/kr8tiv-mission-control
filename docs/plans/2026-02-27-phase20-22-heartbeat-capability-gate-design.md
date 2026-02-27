# Phase 20-22 Heartbeat Stability + Notebook Capability Gate Design

## Scope

This design defines the next GSD reliability sequence after Phase 19:

1. **Phase 20:** heartbeat and channel stability hardening (Telegram timeout reduction).
2. **Phase 21:** NotebookLM capability gate with deterministic preflight and fallback.
3. **Phase 22:** telemetry expansion for measurable continuity/recovery outcomes.

NotebookLM guidance source for this design:
- `docs/operations/2026-02-27-notebooklm-phase20-qna.md`

## Decision Summary

1. The highest-leverage immediate fix is reducing heartbeat instability and runtime restart noise.
2. NotebookLM access must be guarded by explicit capability checks before task execution to avoid silent failures.
3. Persona/identity drift prevention must remain strict and centrally enforced while allowing controlled skill updates.
4. GSD run telemetry needs recovery and continuity metrics so each phase can be validated with hard evidence.

## Phase Breakdown

### Phase 20: Heartbeat + Channel Runtime Stability

Primary outcomes:
1. Heartbeat cycles stay lightweight and deterministic.
2. Telegram remains primary ingress in `phase1`; unused WhatsApp paths stop generating restart noise.
3. Runtime patching remains backward-compatible across OpenClaw config schema variants.

Target controls:
1. Keep heartbeat defaults conservative (`20m`, reasoning off by default for liveness checks).
2. Enforce Telegram config write locks.
3. Disable WhatsApp account-level runtime behavior when channel is not enabled.
4. Add explicit telemetry/events for poller ownership conflicts and heartbeat timeout bursts.

### Phase 21: NotebookLM Capability Gate

Primary outcomes:
1. Notebook-enabled task modes run only when NotebookLM prerequisites pass.
2. Auth/config/tooling failures are surfaced as deterministic blocked states (never silent).
3. Retry behavior is bounded and reason-coded.

Target controls:
1. Preflight checks for profile validity, runner availability, and notebook reachability.
2. Fail-fast classification: retryable vs misconfiguration vs hard-fail.
3. Safe fallback behavior for query/create modes and explicit operator comments.
4. Capability state visibility in API + UI.

### Phase 22: GSD Recovery/Continuity Telemetry

Primary outcomes:
1. Phase-over-phase proof of improved continuity and lower churn.
2. Recovery metrics become first-class fields in GSD runs.
3. Rollout evidence links and metric snapshots stay attached to each run.

Target controls:
1. Persist metrics: incidents, recovered/failed, suppressed, retries, latency, tool failures.
2. Add API/schema support for metric updates.
3. Add dashboard view/query support for run-level health deltas.

## Guardrails (Carry Forward)

1. Persona precedence remains strict: `SOUL.md > USER.md > IDENTITY.md > AGENTS.md`.
2. Runtime config writes remain disabled (`commands.config=false`).
3. Locked model policy and template sync continue drift auto-revert behavior.
4. Deployment remains immutable-tag only with post-rollout health/continuity checks.

## Rollout Order

1. Implement Phase 20 in branch and verify focused tests.
2. Deploy immutable images and validate runtime/log improvements.
3. Implement Phase 21 capability gate and negative-path tests.
4. Implement Phase 22 telemetry migration/API/UI and validate reporting.
