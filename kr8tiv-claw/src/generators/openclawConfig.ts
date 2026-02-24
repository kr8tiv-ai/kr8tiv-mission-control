import type { HarnessSpec } from "../types";

export function buildOpenclawConfig(spec: HarnessSpec): Record<string, unknown> {
  return {
    update: {
      channel: spec.updates.channel,
    },
    gateway: {
      auth: {
        mode: "token",
      },
      pairing: {
        required: spec.channels.dmPairingRequired,
      },
      group: {
        mentionGating: spec.channels.mentionGating,
      },
    },
    agents: {
      defaults: {
        sandbox: {
          nonMainSessions: spec.tools.sandboxNonMainSessions ? "strict" : "off",
        },
        tools: {
          allow: spec.tools.allowlist,
          deny: spec.tools.denylist,
        },
      },
    },
    channels: {
      allow: spec.channels.allow,
      defaults: {
        heartbeat: {
          showOk: true,
          showAlerts: true,
          useIndicator: true,
        },
      },
    },
    kr8tiv: {
      tenant: spec.tenant.slug,
      observability: {
        ownerWebhookUrl: spec.observability.ownerWebhookUrl ?? null,
        managementWebhookUrl: spec.observability.managementWebhookUrl ?? null,
      },
      supermemory: {
        enabled: spec.supermemory.enabled,
        apiKeyEnv: spec.supermemory.apiKeyEnv,
        baseUrl: spec.supermemory.baseUrl,
        topK: spec.supermemory.topK,
        threshold: spec.supermemory.threshold,
      },
    },
  };
}

export function buildSkillPackManifest(
  spec: HarnessSpec,
  tenantId: string,
): Record<string, unknown> {
  return {
    version: 1,
    tenantId,
    installRoot: "<workspace>/skills",
    packs: spec.skills.packs.map((pack) => ({
      name: pack.name,
      source: pack.source,
      version: pack.version ?? "latest",
    })),
  };
}
