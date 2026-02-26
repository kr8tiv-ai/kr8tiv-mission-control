# Phase 18 Recovery Scheduler Migration Gate Design

## Objective

Eliminate startup race noise where webhook worker scheduler runs recovery queries before startup migrations complete.

## Problem Statement

In current startup sequence, backend runs Alembic migrations while webhook worker may start its periodic recovery scheduler immediately. This can briefly produce `UndefinedColumn` errors if scheduler queries a column introduced by a migration that has not finished yet.

## Approaches Considered

1. Fixed startup delay
   - Pros: simple.
   - Cons: non-deterministic and environment-sensitive; can still race on slow migrations.
2. Schema-column probe only
   - Pros: closer to readiness than time delay.
   - Cons: tied to specific columns; brittle as schema evolves.
3. Alembic head gate (recommended)
   - Pros: deterministic and migration-aware; future-proof for additional revisions.
   - Cons: small added check logic in worker path.

## Chosen Design

Use an Alembic head gate before scheduler execution:

1. Read expected migration head from local Alembic script directory.
2. Read current DB revision from `alembic_version`.
3. Allow scheduler only when `current_revision == head_revision`.
4. Cache successful readiness in-process to avoid repeated checks.
5. While gate is closed, skip scheduler tick quietly and continue queue processing.

## Data Flow

1. Worker loop checks periodic scheduler due time.
2. Before running scheduler tick:
   - call `is_scheduler_migration_ready()`.
3. If false:
   - log deferred event and return to queue processing.
4. If true:
   - run scheduler tick normally.

## Safety and Compatibility

1. Queue/webhook processing continues even when scheduler is deferred.
2. Manual recovery API behavior remains unchanged.
3. Gate enables once per process and stays open until restart.

## Testing Strategy

1. Unit tests for migration gate:
   - match head => ready true
   - mismatch => ready false
   - success caching => avoids repeated fetch.
2. Worker tests:
   - enabled + migration ready => scheduler executes
   - enabled + migration pending => scheduler does not execute
   - disabled => no scheduler execution.
