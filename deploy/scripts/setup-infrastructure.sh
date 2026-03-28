#!/bin/bash

# KR8TIV AI Infrastructure Setup Script
# Installs monitoring, logging, backup automation, and recovery orchestration.

set -euo pipefail

echo "========================================="
echo "KR8TIV AI Infrastructure Setup"
echo "========================================="
echo ""

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root or with sudo"
  exit 1
fi

echo "=== Step 1: Installing Uptime Kuma (Monitoring) ==="
docker run -d \
  --name uptime-kuma \
  --restart unless-stopped \
  -p 3001:3001 \
  -v uptime-kuma:/app/data \
  louislam/uptime-kuma:1 || true

echo "Uptime Kuma installed at http://YOUR_IP:3001"
echo ""

echo "=== Step 2: Installing Dozzle (Log Aggregation) ==="
docker run -d \
  --name dozzle \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -p 9999:8080 \
  amir20/dozzle:latest || true

echo "Dozzle installed at http://YOUR_IP:9999"
echo ""

echo "=== Step 3: Setting up automated backups ==="
mkdir -p /backups
cp scripts/backup-containers.sh /root/backup-containers.sh
chmod +x /root/backup-containers.sh

(crontab -l 2>/dev/null | grep -v backup-containers.sh; echo "0 2 * * * /root/backup-containers.sh >> /var/log/container-backup.log 2>&1") | crontab -

echo "Daily backups configured (2 AM)"
echo ""

echo "=== Step 4: Setting up deterministic recovery orchestration ==="
cp scripts/agent-recovery-orchestrator.sh /root/agent-recovery-orchestrator.sh
chmod +x /root/agent-recovery-orchestrator.sh

# Run every 2 minutes. Script uses lock + cooldown to avoid collision loops.
(crontab -l 2>/dev/null | grep -v agent-recovery-orchestrator.sh; echo "*/2 * * * * /root/agent-recovery-orchestrator.sh >> /var/log/agent-recovery-cron.log 2>&1") | crontab -

echo "Recovery orchestrator configured (every 2 minutes)"
echo ""

echo "=== Step 5: Enabling auto-restart on all containers ==="
containers=$(docker ps --format '{{.Names}}' | grep -v -E '(uptime-kuma|dozzle)' || true)

for container in $containers; do
  echo "Setting restart policy for: $container"
  docker update --restart=unless-stopped "$container" >/dev/null
done

echo "Auto-restart enabled on all containers"
echo ""

echo "========================================="
echo "Setup Complete"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Visit http://YOUR_IP:3001 to configure Uptime Kuma"
echo "2. Visit http://YOUR_IP:9999 to view logs"
echo "3. Configure Telegram/Slack alerts in Uptime Kuma"
echo "4. Verify /var/log/agent-recovery.log after first orchestrator run"
echo ""
echo "Backup location: /backups"
echo "Backup schedule: Daily at 2 AM"
echo "Recovery check schedule: Every 2 minutes"
