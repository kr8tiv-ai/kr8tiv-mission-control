#!/usr/bin/env bash
set -euo pipefail

: "${VPS_HOST:?missing VPS_HOST}"
: "${VPS_USER:?missing VPS_USER}"
: "${VPS_SSH_KEY:?missing VPS_SSH_KEY}"
: "${DEPLOY_ROOT:?missing DEPLOY_ROOT}"
: "${COMPOSE_FILE:=compose.yml}"

SSH_OPTS=(-i "$VPS_SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
REMOTE_BASE_CMD="cd '$DEPLOY_ROOT' && docker compose -f '$COMPOSE_FILE'"

echo "Deploying OpenClaw stack to ${VPS_USER}@${VPS_HOST}:${DEPLOY_ROOT}"
ssh "${SSH_OPTS[@]}" "$VPS_USER@$VPS_HOST" "mkdir -p '$DEPLOY_ROOT'"
ssh "${SSH_OPTS[@]}" "$VPS_USER@$VPS_HOST" "$REMOTE_BASE_CMD pull"
ssh "${SSH_OPTS[@]}" "$VPS_USER@$VPS_HOST" "$REMOTE_BASE_CMD up -d --remove-orphans"
ssh "${SSH_OPTS[@]}" "$VPS_USER@$VPS_HOST" "$REMOTE_BASE_CMD ps"

