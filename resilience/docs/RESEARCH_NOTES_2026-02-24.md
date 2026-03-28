# Research Notes (2026-02-24)

This note captures external references used to keep KR8TIV docs aligned with current platform behavior.

## OpenClaw Docs and Runtime

- Source: https://docs.openclaw.ai
- Latest release visible from docs navigation: `v0.4.6` (GitHub releases link from docs homepage).
- Relevant runtime guidance used:
  - Workspace file contracts (`AGENTS.md`, `SOUL.md`, `TOOLS.md`, `USER.md`, `HEARTBEAT.md`, `TASKS.md`).
  - Model failover behavior and provider fallback handling.
  - Tool and auth configuration surfaces.

## Prompt Optimization Research Inputs

- PromptWizard repository:
  - https://github.com/microsoft/PromptWizard
  - Used as reference for iterative prompt optimization loops, evaluation-first changes, and controlled promotion.

- Paper requested:
  - https://arxiv.org/pdf/2510.04618
  - Used as reference direction for stronger autonomous orchestration and reliability-focused iteration loops.

## Integration Decisions Derived

- Keep Mission Control as promotion/rollback authority for prompt/model policy updates.
- Keep OpenClaw runtime focused on execution, not autonomous policy mutation.
- Enforce strict model route locks per agent unless a fallback is explicitly declared and approved.
- Keep all public repos secret-free; inject keys from desktop/VPS runtime only.
