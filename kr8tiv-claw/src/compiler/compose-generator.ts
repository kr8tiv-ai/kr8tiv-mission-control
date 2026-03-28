import type { HarnessConfig } from './schema.js';

function renderWatchdogService(cfg: HarnessConfig): string {
  if (!cfg.watchdog.enabled) return '';

  return `
  agent-watchdog:
    image: curlimages/curl:8.10.1
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    environment:
      WATCHDOG_WEBHOOK_URL: ${cfg.watchdog.webhookUrl}
      WATCHDOG_INTERVAL_SECONDS: "${cfg.watchdog.intervalSeconds}"
      TENANT_ID: ${cfg.tenantId}
    command: >-
      sh -c 'while true; do
        ts=$(date -u +%FT%TZ);
        payload=$(printf "{\\"tenantId\\":\\"%s\\",\\"timestamp\\":\\"%s\\",\\"status\\":\\"alive\\"}" "$TENANT_ID" "$ts");
        curl -fsS -X POST "$WATCHDOG_WEBHOOK_URL" -H "content-type: application/json" -d "$payload" || true;
        sleep "$WATCHDOG_INTERVAL_SECONDS";
      done'
    depends_on:
      openclaw-gateway:
        condition: service_healthy
`;
}

/**
 * Produces a tenant-scoped compose template.
 * The gateway follows upstream image usage, while tenant persistence and health checks
 * are distribution-level defaults.
 */
export function generateTenantCompose(cfg: HarnessConfig): string {
  return `version: "3.9"
services:
  openclaw-gateway:
    image: ${cfg.openclaw.image}
    container_name: openclaw-${cfg.tenantId}
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    environment:
      OPENCLAW_GATEWAY_TOKEN: \${OPENCLAW_GATEWAY_TOKEN}
      OPENCLAW_WORKSPACE: /workspace
      MISSION_CONTROL_URL: ${cfg.controlPlane.missionControlUrl}
      MISSION_CONTROL_TOKEN_FILE: ${cfg.controlPlane.missionControlTokenFile}
      MISSION_CONTROL_TIER: ${cfg.controlPlane.tier}
      MISSION_CONTROL_PACK_REF: ${cfg.controlPlane.packRef}
      MISSION_CONTROL_TELEMETRY_ENABLED: "${cfg.controlPlane.telemetry.enabled}"
      MISSION_CONTROL_CROSS_TENANT_LEARNING: "${cfg.controlPlane.privacy.crossTenantLearning}"
      MISSION_CONTROL_CROSS_USER_LEARNING: "${cfg.controlPlane.privacy.crossUserLearning}"
    volumes:
      - tenant-${cfg.tenantId}-state:/state
      - tenant-${cfg.tenantId}-workspace:/workspace
      - \${MISSION_CONTROL_TOKEN_HOST_PATH:-./secrets/mission_control_token}:${cfg.controlPlane.missionControlTokenFile}:ro
    healthcheck:
      test: ["CMD-SHELL", "node dist/index.js health --token $OPENCLAW_GATEWAY_TOKEN"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s${renderWatchdogService(cfg)}

volumes:
  tenant-${cfg.tenantId}-state:
  tenant-${cfg.tenantId}-workspace:
`;
}
