# Prompt Evolution Gate (Mission Control)

## Vision

Mission Control becomes the central control plane for **all** prompt/context evolution across agent teams.

Instead of each agent drifting independently, Mission Control manages:
- telemetry collection
- evaluation/scoring
- challenger generation
- promotion/rollback
- privacy boundaries

This supports both:
- **Individuals** (single-user, tenant-private learning)
- **Enterprise** (org-wide governance with workspace/team scopes)

## Why centralize here?

- One measurable source of truth for quality and safety
- No hidden agent-specific prompt mutations
- Reproducible deployments and audits
- Shared infrastructure for any model provider

## Functional Architecture

### 1) Prompt Registry Service
Stores versioned prompt/context packs with states:
- `champion`
- `challenger`
- `archived`

Scopes:
- `global`
- `segment` (`individual`, `enterprise`)
- `domain`
- `agent`
- `tenant`

### 2) Telemetry Ingestion
Per task execution, store:
- input/output traces (redacted where required)
- model, latency, token/cost metrics
- tool usage
- outcome metadata (success/failure/retry)

### 3) Evaluation Engine
Auto-scores outputs with policy/rubric checks:
- task completion quality
- format adherence
- safety/policy checks
- latency/cost budget checks

### 4) Optimizer Worker
PromptWizard-style candidate generation and refinement from failure buffers + eval sets.

### 5) Promotion Gate
Only promote challenger when all pass:
- quality threshold improvement
- no safety regression
- budget guardrails respected

### 6) Runtime Injector
At execution time, Mission Control resolves and injects effective champion pack by scope hierarchy.

## Suggested Data Model (MVP)

- `prompt_packs`
- `prompt_versions`
- `task_eval_scores`
- `optimization_runs`
- `promotion_events`

## Implementation Status (2026-02-24)

Phase-2/3 scaffolding is now in-progress in code:
- Prompt registry tables + Alembic migration
- Prompt evolution API endpoints (packs, versions, promote, task eval listing)
- Task completion telemetry hook on status transitions to `done`
- Evaluator queue scaffold (`prompt_eval_task`) with deterministic baseline scoring worker
- Promotion guardrails (min score delta + non-regression checks, with explicit `force` override)
- Manual promotion gate endpoint (auto-promotion intentionally deferred)
- Frontend board-level Prompt Evolution panel route for visibility

## MVP Rollout Plan

### Phase 1 (now): docs + alignment
- Publish architecture in README/docs
- Align `kr8tivclaw` compile defaults to route through Mission Control

### Phase 2: evaluator + telemetry
- Add scoring pipeline for completed tasks
- Add dashboard metrics (quality, regression, cost, latency)

### Phase 3: registry + gate
- Add champion/challenger registry and controlled rollout APIs
- Add rollback support and audit trail

### Phase 4: automated optimization
- Nightly optimizer jobs by scope
- Human approval option for enterprise high-risk workflows

## Privacy and Multi-Tenancy

- Tenant-private data remains isolated by default
- Enterprise orgs can opt into org-level pooling
- Individuals never cross-train with other tenants by default

## Cost Control

- Optimization jobs have explicit per-tenant/per-org budgets
- Use lower-cost models for candidate generation, stronger judges only when needed
- Hard stop when budget threshold is reached

## Outcome

Mission Control becomes the measurable, safe, scalable backbone for continuous agent improvement across the KR8TIV ecosystem and MeetYourKin deployments.
