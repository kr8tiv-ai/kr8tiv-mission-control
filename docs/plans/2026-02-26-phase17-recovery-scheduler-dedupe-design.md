# Phase 17 Recovery Scheduler + Alert Dedupe Design

## Scope

Phase 17 extends Phase 16 by moving recovery from manual/on-demand into continuous background operation with bounded alert noise.

This phase adds:

1. A periodic recovery sweep loop in runtime.
2. Alert deduplication windows to avoid repeated owner pings for the same incident pattern.
3. Policy + config controls to tune behavior without code edits.

## Goals

1. Recovery runs automatically without operator-triggered `/run`.
2. Repeated stale/unreachable incidents for the same agent do not spam Telegram/WhatsApp/UI.
3. Existing Phase 16 APIs remain backward-compatible.
4. Rollout stays deterministic and safe with bounded intervals and conservative defaults.

## Architecture

### 1) Recovery Loop Execution

- Integrate a periodic loop into the webhook worker runtime.
- Each interval:
  - enumerate boards,
  - run `RecoveryEngine.evaluate_board(board_id=...)`,
  - route alerts for incident outcomes.
- Use one in-process loop in the worker to avoid introducing another container in this phase.

### 2) Dedupe Window Policy

- Add `alert_dedupe_seconds` to `RecoveryPolicy` (organization-scoped).
- Use this window to suppress repeated alert delivery for incidents that match:
  - `board_id`
  - `agent_id`
  - `status`
  - `reason`
- Suppression affects alert emission only; incidents are still persisted for auditability.

### 3) Control Surface

- Add runtime config settings:
  - `recovery_loop_enabled` (default `true`)
  - `recovery_loop_interval_seconds` (default `180`)
- Expose `alert_dedupe_seconds` via existing policy read/update API payloads.

## Data Flow

1. Worker loop wakes on configured interval.
2. Scheduler runs recovery engine on each board.
3. Engine persists incidents.
4. For each incident:
   - skip alert if status is `suppressed`,
   - check dedupe window against recent matching incidents,
   - if not duplicate, send via `RecoveryAlertService` routing order.

## Error Handling

1. Board-level failures are logged and isolated; one board failure does not stop the sweep.
2. Alert delivery exceptions remain non-fatal and use existing fallback behavior.
3. Loop exceptions are caught and retried on next interval.
4. Invalid/negative interval values are clamped to safe minimums.

## Testing Strategy

1. Unit tests for policy/schema changes (`alert_dedupe_seconds` defaults + update path).
2. Service tests for scheduler sweep behavior and dedupe suppression logic.
3. Worker-loop tests for “scheduler tick executes when enabled”.
4. Regression tests to keep existing Phase 16 recovery endpoints green.

## Rollout Strategy

1. Merge with defaults that are safe (`enabled=true`, moderate interval, finite dedupe).
2. Deploy immutable images and verify:
   - health/ready endpoints,
   - policy API includes dedupe field,
   - incidents still persist,
   - manual `/run` remains functional.
3. Observe live logs for one interval cycle and confirm no alert storm behavior.
