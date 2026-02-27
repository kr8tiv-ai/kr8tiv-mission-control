# Phase 26 Rollout Recovery Probe Design

Date: 2026-02-27
Owner: Mission Control Runtime

## Goal

Close the operational gap where deploy actions show success but runtime verification cannot be completed due to unavailable host shell access.

## Problem

Current runtime verification checks API route presence and NotebookLM capability, but does not validate externally reachable runtime endpoints as first-class harness checks.

In blocked host environments, this leads to ambiguous rollout state:
- deploy action success
- no shell evidence
- public runtime remains unreachable

## Proposed Design

Add an optional external health probe gate to `run_verification_harness`.

Behavior:
1. Read `VERIFICATION_EXTERNAL_HEALTH_URLS` from env (comma-separated URLs).
2. If unset:
   - emit check `external_health_probe`
   - `required=false`, `passed=true`, `detail=skipped:unconfigured`
3. If set:
   - probe each URL with bounded timeout
   - fail on timeout/exception/non-success status
   - emit required check result:
     - success: `detail=ok:<count>`
     - failure: `detail=failed:<url>=<reason>;...`
4. Preserve existing harness behavior for route checks and NotebookLM capability.

## Why This Design

1. Deterministic rollout signal without requiring shell access.
2. Backward compatible when env is unset.
3. Fits existing verification matrix semantics (required/non-required checks).
4. Provides immediate operator-readable failure detail for degraded-mode decisions.

## Non-Goals

1. Replacing host-shell diagnostics.
2. Managing VPS Docker lifecycle from harness.
3. Changing existing GSD gate wiring semantics.

## Acceptance Criteria

1. Harness always emits `external_health_probe`.
2. Unconfigured mode is non-blocking.
3. Configured failure increments `required_failed`.
4. Configured success preserves pass state.
5. Existing verification API tests remain green.
