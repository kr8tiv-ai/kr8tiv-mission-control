# KR8TIV AI Team Setup and Organization

Operational infrastructure templates and runbooks for running KR8TIV AI agent stacks on VPS Docker hosts.

## What this repo provides

- Base infrastructure setup script for Docker host hardening and core services
- Monitoring and tunnel runbooks
- Docker Compose templates for agent stacks and Mission Control
- Backup script for container data
- Deterministic agent recovery orchestrator script
- Task mode + arena + NotebookLM operating notes

## Repository layout

```text
team-setup-and-organization/
  docker-templates/
    agent-template.yml
    mission-control.yml
  docs/
    INFRASTRUCTURE.md
    CLOUDFLARE-TUNNEL.md
    TASK-MODES-ARENA-NOTEBOOKLM.md
  scripts/
    setup-infrastructure.sh
    backup-containers.sh
    agent-recovery-orchestrator.sh
```

## Quick start

1. Clone repository:

```bash
git clone https://github.com/kr8tiv-ai/team-setup-and-organization.git
cd team-setup-and-organization
```

2. Run infrastructure bootstrap:

```bash
sudo bash scripts/setup-infrastructure.sh
```

3. Review and adapt templates:

- `docker-templates/mission-control.yml`
- `docker-templates/agent-template.yml`

4. Configure backups:

```bash
sudo bash scripts/backup-containers.sh
```

## Operations notes

- Keep all service definitions under version control in this repo before deploying to production.
- Use the docs folder as the source of truth for setup and troubleshooting.
- Validate changes in a staging host before applying to production.

## Documentation index

- Infrastructure: `docs/INFRASTRUCTURE.md`
- Agent resilience: `docs/AGENT-RESILIENCE-RUNBOOK.md`
- Cloudflare tunnel: `docs/CLOUDFLARE-TUNNEL.md`
- Task modes + arena + NotebookLM: `docs/TASK-MODES-ARENA-NOTEBOOKLM.md`

## Contribution

See `CONTRIBUTING.md` for change and review standards.
