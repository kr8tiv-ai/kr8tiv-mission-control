# Agent Resilience Runbook

This runbook defines persistence and deterministic recovery for FRIDAY, ARSENAL, JOCASTA, and EDITH.

## Objectives

- Agents auto-restart on host reboot or process crash.
- Exactly one recovery owner acts when a peer is down.
- Secret values stay out of repo files and are injected at runtime only.
- Model routes remain pinned unless explicitly changed through Mission Control policy.

## Runtime Model Policy

- FRIDAY: `openai-codex/gpt-5.3-codex` (CLI path)
- ARSENAL: `openai-codex/gpt-5.3-codex` (CLI path)
- JOCASTA: `nvidia/moonshotai/kimi-k2.5` (NVIDIA API path)
- EDITH: `google-gemini-cli/gemini-3.1-pro` (CLI path)

Do not let agents self-edit model routes at runtime.

## Recovery Delegation

Recovery order:
1. FRIDAY
2. ARSENAL
3. JOCASTA
4. EDITH

Rules:
- Down agent cannot self-assign recovery.
- Non-owner agents do not run competing restart attempts.
- Recovery attempts are logged with UTC timestamps.

## Required Host Automation

Installed by `scripts/setup-infrastructure.sh`:

- `/root/backup-containers.sh` (daily 2 AM)
- `/root/agent-recovery-orchestrator.sh` (every 2 minutes)

## Verification Commands

```bash
docker ps --format '{{.Names}}|{{.Status}}'
crontab -l | grep -E 'backup-containers|agent-recovery-orchestrator'
tail -n 100 /var/log/agent-recovery.log
tail -n 100 /var/log/container-backup.log
```

## Secret Hygiene

- Keep `docker-templates/*.yml` public-safe.
- Use `*_FILE` env patterns and mounted secret files.
- Do not commit `.env` values, key files, token files, or OAuth caches.

