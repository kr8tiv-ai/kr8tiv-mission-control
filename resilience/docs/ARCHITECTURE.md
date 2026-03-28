# Architecture: Team Execution Resilience

## Objective

Keep FRIDAY, ARSENAL, JOCASTA, and EDITH operational and coordinated under Mission Control even when one agent process, model path, or host service fails.

## Design Principles

- Deterministic over implicit: exactly one recovery owner per incident.
- Secretless git: all committed artifacts are sanitized.
- Personality-safe upgrades: doctrine augments behavior without flattening character.
- Mission Control as control plane; OpenClaw as runtime execution plane.

## Layers

1. Runtime Layer (OpenClaw containers)
- Agent sessions, channels, skills, workspace state.
- Local watchdog and heartbeat loops.

2. Coordination Layer (Mission Control)
- Agent lifecycle status and heartbeat state.
- Delegated recovery assignment and audit trail.
- Board rules and role-based behavior.

3. Persistence Layer (this repo + host storage)
- Public templates, runbooks, policies, and secret scrub tooling.
- Boot bundle generation for fast restore.

## Recovery Assignment Algorithm

Input:
- `down_agent`
- current online peers
- board role metadata

Priority order:
1. FRIDAY (if not down)
2. ARSENAL
3. JOCASTA
4. EDITH

Rules:
- Never assign the down agent to self-recovery.
- Only one assignee per incident.
- If assignee fails, re-elect after cooldown with next candidate.

## Model Policy

- Pinned primary models remain role-specific.
- Default behavior is strict provider affinity:
  - FRIDAY: `openai-codex/gpt-5.3-codex`
  - ARSENAL: `openai-codex/gpt-5.3-codex`
  - JOCASTA: `nvidia/moonshotai/kimi-k2.5`
  - EDITH: `google-gemini-cli/gemini-3.1-pro` (CLI route)
- Cross-provider fallback is blocked by default.
- Optional fallback routes are allowed only when explicitly declared in policy and approved in Mission Control.

## Boot Bundle Contents (Public)

- Sanitized OpenClaw profile templates
- Recovery policy yaml
- Role charters and harness checklists
- Restore runbook and validation scripts

Excluded:
- `.env` values
- API keys / tokens / OAuth caches
- Telegram bot token files

## Acceptance Baseline

- Agent offline is detected within heartbeat window.
- Exactly one peer receives recovery assignment.
- Recovery action is logged and traceable.
- No committed artifact contains secrets.
