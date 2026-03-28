# KR8TIV Team Execution Resilience

Public, secret-free resilience framework for KR8TIV multi-agent operations across Mission Control and OpenClaw.

Repository URL: https://github.com/kr8tiv-ai/kr8tiv-team-execution-resilience

## Scope

- Agent persistence methodology (backup, restore, reboot safety)
- Deterministic recovery ownership (single assignee, no collision)
- Model route lock policy (strict primary pins + controlled fallback gates)
- Public doctrine and harness guidance (no secrets in git)
- Iron Man character-safe operational charters for FRIDAY, ARSENAL, JOCASTA, EDITH

## Non-Negotiables

- This repository must stay public.
- No API keys, bot tokens, OAuth blobs, or private endpoint credentials are committed.
- Secrets are injected from desktop/VPS runtime only.

## Directory Map

- `docs/ARCHITECTURE.md`: reference architecture
- `docs/OPERATIONS_RUNBOOK.md`: day-2 operations and acceptance checks
- `docs/IRON-MAN-AGENT-CHARTERS.md`: personality-safe charters and hierarchy
- `docs/GSD_RALPH_LOOP_PROTOCOL.md`: iterative execution loop protocol
- `docs/RESEARCH_NOTES_2026-02-24.md`: external-source alignment notes
- `config/model-policy.public.yaml`: model pin + fallback policy
- `templates/profiles/*.profile.json`: public, sanitized profile templates
- `scripts/sanitize_openclaw_json.py`: remove secrets from OpenClaw config exports
- `scripts/build_boot_bundle.ps1`: build a secret-free "boot bundle" archive
- `scripts/assign_recovery_owner.py`: deterministic recovery assignee election
- `scripts/validate_public_bundle.py`: fail if secrets are detected in bundle artifacts

## Quick Start

1. Export runtime configs from live agents to a temp folder.
2. Run `scripts/sanitize_openclaw_json.py` over those exports.
3. Run `scripts/build_boot_bundle.ps1` to generate a public boot bundle.
4. Run `scripts/validate_public_bundle.py` to verify no secrets remain.
5. Publish/update the resulting artifact and runbooks.

## Related KR8TIV Repositories

- Mission Control integration: https://github.com/kr8tiv-ai/kr8tiv-mission-control
- OpenClaw distribution layer: https://github.com/kr8tiv-ai/kr8tivclaw
- Infrastructure templates: https://github.com/kr8tiv-ai/team-setup-and-organization
