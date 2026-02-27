# Phase 27 Rollout Gate + Auto-Rollback Design

Date: 2026-02-27
Owner: Mission Control Runtime

## Goal

Prevent false-positive production rollouts where image publish/deploy actions are green but runtime endpoints are down.

## Problem statement

Current publish pipeline guarantees image availability but does not prove live runtime health. This allows:
1. `docker_compose_*` success with dead service ports.
2. Delayed incident detection.
3. Manual rollback dependence under degraded control-plane access.

## Design

Add a post-publish runtime health gate with optional rollback hook:

1. Script: `scripts/ci/rollout_health_gate.py`
   - Probe required URLs with retries.
   - Emit deterministic status: `passed|failed|skipped`.
   - Run rollback command when `failed` and rollback is configured.
   - Persist machine-readable evidence payload.
2. Workflow wiring: `.github/workflows/publish-mission-control-images.yml`
   - Execute gate after image push.
   - Upload evidence artifact on all outcomes.
3. Configuration contracts:
   - `RUNTIME_HEALTH_URLS` (required to enforce gate)
   - `RUNTIME_ROLLBACK_COMMAND` (optional rollback hook)

## Failure semantics

1. `passed`: rollout healthy.
2. `failed`: rollout unhealthy; workflow fails even if rollback succeeds (incident remains visible).
3. `skipped`: no configured health URLs; workflow remains green but explicitly non-validated.

## Why this design

1. Minimal dependencies (stdlib only) for CI reliability.
2. Reusable in any runner context.
3. Explicit forensic evidence for each rollout.
4. Backward compatible with current pipeline.

## Non-goals

1. Full Hostinger API orchestrator in this phase.
2. Replacing host-level diagnostics.
3. Auto-remediation for unknown infrastructure/network ACL failures.

## Acceptance criteria

1. New gate script has unit tests for pass/fail/skipped/rollback semantics.
2. Publish workflow executes gate and uploads evidence artifact.
3. Runtime-image policy docs include gate contracts and status semantics.
