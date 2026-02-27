# 2026-02-27 NotebookLM Phase 27 Q&A

## Scope

This query batch supports the next GSD slice: CI-driven rollout verification with deterministic rollback semantics.

Notebook queried:
- `89e530ae-204e-477e-8f24-b0d2677c708f` (`openclaw fork`)

## Q1
What deterministic CI gate + auto-rollback pattern should we use so image publish success never gets treated as runtime success when service ports are down?

### NotebookLM synthesis
1. Enforce post-publish runtime probes as a required gate.
2. Treat deployment action success as non-authoritative until probe checks pass.
3. Execute rollback only on failed probe matrix.
4. Persist rollout evidence payload for forensics and phase-over-phase reliability tracking.
5. Keep failure semantics explicit:
   - publish success + probe fail == rollout fail
   - rollback attempted does not imply rollout success

Conversation ID: `8ec32bb2-3735-40be-a385-76d5ffa9f455`

## Q2
What minimum evidence payload should be persisted after each rollout attempt?

### NotebookLM synthesis
1. Timestamped probe matrix by URL and attempt.
2. Runtime health status summary (pass/fail/skipped).
3. Rollback metadata (attempted/succeeded/exit_code).
4. Lightweight command/log context for incident triage.
5. Structured artifact output to support continuity analytics.

Conversation ID: `e620f9e2-9a3b-4e85-82b7-8cd66fe4eb9c`

## Phase 27 implementation direction

1. Add stdlib rollout gate script:
   - `scripts/ci/rollout_health_gate.py`
2. Wire gate into publish workflow after image push:
   - `.github/workflows/publish-mission-control-images.yml`
3. Upload evidence artifact on every run:
   - `artifacts/rollout/health-gate.json`
   - `artifacts/rollout/health-gate.env`
4. Keep rollback configurable via:
   - `RUNTIME_HEALTH_URLS`
   - `RUNTIME_ROLLBACK_COMMAND`
