# Persona Integrity Protocol

This protocol prevents identity drift across team and individual agents.

## Precedence Contract

Non-negotiable load order:

1. `SOUL.md`
2. `USER.md`
3. `IDENTITY.md`
4. `AGENTS.md`

If documents conflict, higher-precedence files always win.

## Enforcement Controls

- Baseline checksums are stored per agent in `agent_persona_integrity`.
- Drift checks run during provisioning/sync and can be triggered by runtime workflows.
- Any mismatch in identity file checksums is treated as drift and logged as an integrity event.
- Persona preset changes are auditable through the persona preset API and migration history.

## Reasoning Defaults

- Default reasoning policy is `max`.
- If `max` is unsupported by the active model, fallback resolves to the highest supported mode.
- If no high mode exists, fallback resolves to the model default.
- Heartbeat payloads must include reasoning metadata (`includeReasoning=true`).

## Team vs Individual Mode

- Team mode allows orchestrator behavior.
- Individual mode must disable orchestration gates and run as standalone execution.
- Both modes inherit the same persona integrity and reasoning policy controls.

## Change Control

- Identity-policy updates require explicit change request + review.
- No direct runtime mutation of core persona documents.
- Policy changes must include:
  - tests (or deterministic checks),
  - migration/docs updates when schema changes,
  - deployment notes in production docs.
