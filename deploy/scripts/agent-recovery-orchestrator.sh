#!/bin/bash

# KR8TIV AI - Agent Recovery Orchestrator
# Single-owner deterministic recovery for Friday/Arsenal/Jocasta/Edith.
# Designed for cron execution on the Docker host.

set -euo pipefail

AGENTS=("friday" "arsenal" "jocasta" "edith")
PRIORITY=("friday" "arsenal" "jocasta" "edith")
LOCK_FILE="/var/run/kr8tiv-recovery.lock"
STATE_DIR="/var/run/kr8tiv-recovery"
LOG_FILE="/var/log/agent-recovery.log"
COOLDOWN_SECONDS="${RECOVERY_COOLDOWN_SECONDS:-300}"

mkdir -p "$STATE_DIR"

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE"
}

resolve_container() {
  local agent="$1"
  local candidates=("openclaw-$agent")

  # Handle legacy Friday naming if present.
  if [ "$agent" = "friday" ]; then
    candidates+=("openclaw-ydy8-openclaw-1")
  fi

  for c in "${candidates[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
      echo "$c"
      return 0
    fi
  done

  return 1
}

container_health_state() {
  local container="$1"
  local status health

  status=$(docker inspect --format '{{.State.Status}}' "$container" 2>/dev/null || echo "missing")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null || echo "none")

  echo "$status|$health"
}

is_agent_up() {
  local agent="$1"
  local container state status health

  if ! container=$(resolve_container "$agent"); then
    return 1
  fi

  state=$(container_health_state "$container")
  status="${state%%|*}"
  health="${state##*|}"

  if [ "$status" != "running" ]; then
    return 1
  fi

  if [ "$health" = "unhealthy" ]; then
    return 1
  fi

  return 0
}

elect_owner() {
  local down="$1"
  local owner=""

  for candidate in "${PRIORITY[@]}"; do
    [ "$candidate" = "$down" ] && continue
    if is_agent_up "$candidate"; then
      owner="$candidate"
      break
    fi
  done

  echo "$owner"
}

within_cooldown() {
  local down="$1"
  local stamp_file="$STATE_DIR/${down}.stamp"
  local now last

  now=$(date +%s)
  if [ ! -f "$stamp_file" ]; then
    return 1
  fi

  last=$(cat "$stamp_file" 2>/dev/null || echo 0)
  if [ $((now - last)) -lt "$COOLDOWN_SECONDS" ]; then
    return 0
  fi

  return 1
}

mark_recovery_attempt() {
  local down="$1"
  date +%s > "$STATE_DIR/${down}.stamp"
}

find_down_agent() {
  local agent container state status health

  for agent in "${AGENTS[@]}"; do
    if ! container=$(resolve_container "$agent"); then
      continue
    fi

    state=$(container_health_state "$container")
    status="${state%%|*}"
    health="${state##*|}"

    if [ "$status" != "running" ] || [ "$health" = "unhealthy" ]; then
      echo "$agent|$container|$status|$health"
      return 0
    fi
  done

  return 1
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "Recovery lock busy, another recovery process is active"
  exit 0
fi

if ! result=$(find_down_agent); then
  log "All monitored agents healthy"
  exit 0
fi

down_agent="${result%%|*}"
rest="${result#*|}"
down_container="${rest%%|*}"
rest="${rest#*|}"
down_status="${rest%%|*}"
down_health="${rest##*|}"

if within_cooldown "$down_agent"; then
  log "Cooldown active for $down_agent, skipping recovery attempt"
  exit 0
fi

owner=$(elect_owner "$down_agent")
if [ -z "$owner" ]; then
  log "No healthy owner available to recover $down_agent"
  mark_recovery_attempt "$down_agent"
  exit 1
fi

log "Recovery incident: down_agent=$down_agent container=$down_container status=$down_status health=$down_health owner=$owner"
mark_recovery_attempt "$down_agent"

if docker restart "$down_container" >/dev/null; then
  sleep 10
  post_state=$(container_health_state "$down_container")
  post_status="${post_state%%|*}"
  post_health="${post_state##*|}"
  log "Recovery attempt complete: down_agent=$down_agent owner=$owner post_status=$post_status post_health=$post_health"
else
  log "Recovery restart command failed: down_agent=$down_agent owner=$owner container=$down_container"
  exit 1
fi
