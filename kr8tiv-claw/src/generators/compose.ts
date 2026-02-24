import type { HarnessSpec } from "../types";

export interface ComposeOptions {
  tenantId: string;
  containerTag: string;
  includeWatchdog: boolean;
}

export function buildComposeTemplate(spec: HarnessSpec, options: ComposeOptions): string {
  const lines = [
    "name: " + options.tenantId,
    "",
    "services:",
    "  openclaw-gateway:",
    "    image: ghcr.io/openclaw/openclaw:latest",
    "    restart: unless-stopped",
    "    environment:",
    "      OPENCLAW_GATEWAY_TOKEN: ${OPENCLAW_GATEWAY_TOKEN}",
    "      TENANT_CONTAINER_TAG: " + options.containerTag,
    "      SUPERMEMORY_API_KEY: ${SUPERMEMORY_API_KEY}",
    "    volumes:",
    "      - " + options.tenantId + "_state:/data/state",
    "      - " + options.tenantId + "_workspace:/data/workspace",
    "      - ./openclaw.json:/data/openclaw.json:ro",
    "      - ./workspace:/data/workspace-seed:ro",
    "    healthcheck:",
    '      test: ["CMD-SHELL", "node dist/index.js health --token $$OPENCLAW_GATEWAY_TOKEN"]',
    "      interval: 30s",
    "      timeout: 10s",
    "      retries: 3",
    "      start_period: 20s",
  ];

  if (options.includeWatchdog) {
    lines.push(
      "",
      "  agent-watchdog:",
      "    image: node:22-alpine",
      "    restart: unless-stopped",
      "    working_dir: /app",
      "    environment:",
      "      OPENCLAW_GATEWAY_TOKEN: ${OPENCLAW_GATEWAY_TOKEN}",
      "      OWNER_WEBHOOK_URL: ${OWNER_WEBHOOK_URL}",
      "      MANAGEMENT_WEBHOOK_URL: ${MANAGEMENT_WEBHOOK_URL}",
      "    command:",
      "      - node",
      "      - dist/index.js",
      "      - watchdog",
      "      - --tenant",
      "      - " + options.tenantId,
      "      - --owner-webhook",
      "      - ${OWNER_WEBHOOK_URL}",
      "      - --management-webhook",
      "      - ${MANAGEMENT_WEBHOOK_URL}",
      "      - --interval-seconds",
      "      - " + String(spec.observability.heartbeatIntervalSeconds),
      "    volumes:",
      "      - ./:/app",
      "    depends_on:",
      "      openclaw-gateway:",
      "        condition: service_healthy",
    );
  }

  lines.push(
    "",
    "volumes:",
    "  " + options.tenantId + "_state:",
    "  " + options.tenantId + "_workspace:",
    "",
  );
  return lines.join("\n");
}
