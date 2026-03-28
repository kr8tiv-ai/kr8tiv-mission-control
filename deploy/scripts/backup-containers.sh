#!/bin/bash

# KR8TIV AI - Container Backup Script
# Runs daily via cron to back up agent state and Mission Control database.
# Retention: 7 days

set -euo pipefail

DATE=$(date +%Y%m%d)
STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BACKUP_DIR="/backups"
MANIFEST="$BACKUP_DIR/backup-manifest-$DATE.txt"

mkdir -p "$BACKUP_DIR"

echo "Starting backup at $STAMP"

# Update this list when new agents are deployed.
AGENTS=("friday" "arsenal" "edith" "jocasta")

for agent in "${AGENTS[@]}"; do
  container="openclaw-$agent"
  data_path="/docker/openclaw-$agent/data"
  out_file="$BACKUP_DIR/openclaw-$agent-$DATE.tar.gz"

  if [ -d "$data_path" ]; then
    echo "Backing up $container from $data_path"
    tar -czf "$out_file" "$data_path"
    sha256sum "$out_file" >> "$MANIFEST"
  else
    echo "WARNING: $data_path not found, skipping $container"
  fi
done

echo "Backing up Mission Control database"
db_out="$BACKUP_DIR/mission-control-db-$DATE.sql"
if docker ps --format '{{.Names}}' | grep -q '^openclaw-mission-control-db-1$'; then
  docker exec openclaw-mission-control-db-1 \
    pg_dump -U postgres mission_control \
    > "$db_out"
  sha256sum "$db_out" >> "$MANIFEST"
else
  echo "WARNING: openclaw-mission-control-db-1 not running, DB backup skipped"
fi

echo "Cleaning up backups older than 7 days"
find "$BACKUP_DIR" -name "openclaw-*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "mission-control-db-*.sql" -mtime +7 -delete
find "$BACKUP_DIR" -name "backup-manifest-*.txt" -mtime +7 -delete

echo "Backup completed at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
du -sh "$BACKUP_DIR"

# Optional: mirror backup directory to remote object storage.
# aws s3 sync "$BACKUP_DIR" s3://your-bucket/backups/
