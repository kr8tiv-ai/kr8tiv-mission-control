#!/usr/bin/env bash
set -euo pipefail

CONTAINERS="${OPENCLAW_CONTAINERS:-openclaw-arsenal openclaw-edith openclaw-jocasta openclaw-ydy8-openclaw-1}"
PROJECT_NAME="${OPENCLAW_PROJECT_NAME:-kr8tiv-mission-control}"
RECHECK_SECONDS="${OPENCLAW_RECHECK_SECONDS:-15}"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log_event() {
  local level="$1"
  local container="$2"
  local action="$3"
  local message="$4"
  printf '{"ts":"%s","level":"%s","container":"%s","action":"%s","message":"%s"}\n' "$(timestamp)" "$level" "$container" "$action" "$message"
}

container_status() {
  local container="$1"
  docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null || true
}

check_one_container() {
  local container="$1"
  local status_health
  status_health="$(container_status "$container")"
  if [[ -z "$status_health" ]]; then
    log_event "warn" "$container" "restart_container" "Container missing, attempting start"
    docker start "$container" >/dev/null 2>&1 || true
    return
  fi

  local status="${status_health%%|*}"
  local health="${status_health##*|}"
  if [[ "$status" != "running" || "$health" == "unhealthy" || "$health" == "starting" || "$health" == "none" ]]; then
    log_event "warn" "$container" "restart_container" "status=$status health=$health"
    docker restart "$container" >/dev/null
    sleep "$RECHECK_SECONDS"
    status_health="$(container_status "$container")"
    status="${status_health%%|*}"
    health="${status_health##*|}"
    if [[ "$status" != "running" || "$health" == "unhealthy" || "$health" == "starting" ]]; then
      log_event "error" "$container" "restart_project" "Escalating project restart after failed container restart"
      docker compose -p "$PROJECT_NAME" restart >/dev/null || true
    fi
  else
    log_event "info" "$container" "noop" "healthy"
  fi
}

for container in $CONTAINERS; do
  check_one_container "$container"
done

