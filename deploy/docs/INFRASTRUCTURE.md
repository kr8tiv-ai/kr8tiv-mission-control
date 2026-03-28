# Infrastructure Guide

Complete walkthrough of the KR8TIV AI infrastructure setup.

---

## Architecture Overview

Our infrastructure is designed for autonomous AI agent teams:

- **Agent Layer**: 4+ OpenClaw containers (Friday, Arsenal, EDITH, Jocasta)
- **Orchestration Layer**: Mission Control (FastAPI + PostgreSQL + Redis)
- **Monitoring Layer**: Uptime Kuma + Dozzle
- **Backup Layer**: Automated daily backups with 7-day retention
- **Recovery Layer**: Deterministic single-owner restart orchestration

---

## Task Mode Orchestration (Arena + NotebookLM)

Mission Control task modes require explicit runtime config in both API and worker services:

```yaml
ARENA_ALLOWED_AGENTS: friday,arsenal,edith,jocasta
ARENA_REVIEWER_AGENT: arsenal
NOTEBOOKLM_RUNNER_CMD: uvx --from notebooklm-mcp-cli@latest nlm
NOTEBOOKLM_PROFILES_ROOT: /var/lib/notebooklm/profiles
NOTEBOOKLM_TIMEOUT_SECONDS: 120
```

Use the dedicated runbook for rollout and hardening:
- [Task Modes + Arena + NotebookLM](TASK-MODES-ARENA-NOTEBOOKLM.md)

---

## Core Components

### 1. Docker Auto-Restart

**What it does:** Automatically restarts containers when they crash.

**Configuration:**
```yaml
services:
  agent:
    restart: unless-stopped
```

**Apply to existing containers:**
```bash
docker update --restart=unless-stopped container-name
```

**Why it matters:** Without this, a crashed container stays down until manual intervention. With it, containers auto-recover in seconds.

---

### 2. Health Checks

**What it does:** Monitors container health and triggers restart if unhealthy.

**Configuration:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:48650/healthz"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

**Types of checks:**
- HTTP endpoint: `curl -f http://localhost:PORT/healthz`
- Database: `pg_isready -U postgres`
- Redis: `redis-cli ping`
- TCP port: `nc -z localhost PORT`

**Why it matters:** Catches "zombie" processes — containers that are technically running but not responding.

---

### 3. Uptime Kuma

**What it does:** Monitors all services and sends alerts when issues are detected.

**Access:** `http://YOUR_IP:3001`

**Setup:**
1. Create admin account on first visit
2. Add monitors for each service:
   - Type: HTTP(s)
   - URL: `http://localhost:PORT/healthz`
   - Interval: 60 seconds
3. Add notification channels (Telegram, Slack, Discord, Email)

**Example monitors:**
- Friday: `http://localhost:48650/healthz`
- Arsenal: `http://localhost:48652/healthz`
- Mission Control: `http://localhost:8100/healthz`
- Frontend: `http://localhost:3100`

**Why it matters:** You get alerted immediately when something goes down, not 14 hours later.

---

### 4. Dozzle

**What it does:** Provides a web UI for all container logs in real-time.

**Access:** `http://YOUR_IP:9999`

**Features:**
- Real-time log streaming
- Search & filter
- Multi-container view
- No configuration needed

**Usage:**
1. Open Dozzle in browser
2. Select container from sidebar
3. View logs, search for errors, copy/download as needed

**Why it matters:** Debugging is 10x faster when all logs are in one place.

---

### 5. Automated Backups

**What it does:** Daily backups of all agent data and databases.

**Configuration:** See `scripts/backup-containers.sh`

**Schedule:** Daily at 2 AM via cron

**Retention:** 7 days (older backups auto-deleted)

**Location:** `/backups/`

**Contents:**
- All agent data volumes (compressed .tar.gz)
- Mission Control PostgreSQL database (SQL dump)

**Manual backup:**
```bash
sudo /root/backup-containers.sh
```

**Restore:**
```bash
# Extract agent data
tar -xzf /backups/openclaw-friday-YYYYMMDD.tar.gz -C /

# Restore database
docker exec -i openclaw-mission-control-db-1 \
  psql -U postgres mission_control < /backups/mission-control-db-YYYYMMDD.sql
```

**Why it matters:** Hardware fails. Humans make mistakes. Backups save you.

---

### 6. Deterministic Recovery Orchestrator

**What it does:** Detects down or unhealthy agents and performs one-owner recovery attempts with cooldown and logging.

**Configuration:** See `scripts/agent-recovery-orchestrator.sh`

**Schedule:** Every 2 minutes via cron

**Logs:** `/var/log/agent-recovery.log`

**Recovery order:** FRIDAY -> ARSENAL -> JOCASTA -> EDITH

**Why it matters:** Prevents recovery collisions and guarantees consistent restore behavior.

---

## Network Security

### Current Setup (Good)
- Containers in isolated Docker networks
- Only necessary ports exposed
- Secrets encrypted at rest

### Recommended (Better)
- Use Cloudflare Tunnel for HTTPS access (see [CLOUDFLARE-TUNNEL.md](CLOUDFLARE-TUNNEL.md))
- Enable UFW firewall on all non-tunnel ports
- Rotate API keys monthly

---

## Resource Limits

**Per container limits:**
```yaml
deploy:
  resources:
    limits:
      memory: 4G
    reservations:
      memory: 2G
```

**Monitor usage:**
```bash
docker stats
```

**Why it matters:** Prevents one container from consuming all server resources.

---

## Troubleshooting

### Container keeps restarting
```bash
# View logs
docker logs container-name --tail=100

# Check health status
docker inspect container-name --format='{{.State.Health.Status}}'

# View health check output
docker inspect container-name --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

### Database connection errors
```bash
# Check if database is healthy
docker exec openclaw-mission-control-db-1 pg_isready -U postgres

# Check connection from backend
docker exec openclaw-mission-control-backend-1 \
  curl -f http://db:5432 || echo "Cannot reach database"
```

### Out of memory
```bash
# Check current usage
docker stats --no-stream

# Check system memory
free -h

# Check swap
swapon --show
```

---

## Maintenance Tasks

### Weekly
- [ ] Review Uptime Kuma for any downtime patterns
- [ ] Check backup logs: `tail -100 /var/log/container-backup.log`
- [ ] Review Dozzle for repeated errors

### Monthly
- [ ] Update Docker images: `docker compose pull && docker compose up -d`
- [ ] Rotate API keys in vault
- [ ] Review disk usage: `df -h`
- [ ] Test disaster recovery (restore from backup to staging)

### Quarterly
- [ ] Security audit (update dependencies, review exposed ports)
- [ ] Performance review (optimize resource limits)
- [ ] Capacity planning (scale up if needed)

---

## Scaling Up

### Adding a New Agent

1. Copy agent template: `cp docker-templates/agent-template.yml docker/openclaw-newagent/docker-compose.yml`
2. Customize environment variables
   - Use `*_FILE` runtime secret injection variables.
   - Do not place literal keys or tokens in compose files.
3. Deploy: `cd docker/openclaw-newagent && docker compose up -d`
4. Add monitor in Uptime Kuma
5. Update backup script with new agent name

### Adding a New Server

1. Clone infrastructure setup to new server
2. Run `scripts/setup-infrastructure.sh`
3. Configure Cloudflare Tunnel for secure access
4. Add server monitors in Uptime Kuma

---

## Best Practices

✅ **Always** run health checks on production containers  
✅ **Always** enable auto-restart  
✅ **Always** monitor logs via Dozzle  
✅ **Always** set up alerts in Uptime Kuma  
✅ **Always** test backups monthly  

❌ **Never** expose database ports publicly  
❌ **Never** hardcode secrets in docker-compose files  
❌ **Never** skip health checks to "save resources"  
❌ **Never** disable auto-restart "temporarily"  

---

## Questions?

Open an issue or reach out: [kr8tiv.ai/contact](https://kr8tiv.ai/contact)
