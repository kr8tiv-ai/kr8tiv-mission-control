import type { HarnessSpec } from "../types";

function renderList(items: string[]): string {
  if (items.length === 0) {
    return "- none";
  }
  return items.map((item) => `- ${item}`).join("\n");
}

export function renderAgentsMd(spec: HarnessSpec): string {
  return `# AGENTS

## Identity
- Name: ${spec.tenant.displayName}
- Role: ${spec.identity.role}
- Purpose: ${spec.identity.purpose}
- Personality: ${spec.identity.personality}

## Responsibilities
${renderList(spec.jobFunctions.responsibilities)}

## Success Criteria
${renderList(spec.jobFunctions.successCriteria)}

## Channel Policy
- Allowed channels: ${spec.channels.allow.join(", ")}
- DM pairing required: ${spec.channels.dmPairingRequired}
- Mention gating: ${spec.channels.mentionGating}

## Tool Policy
- Allowlist:
${renderList(spec.tools.allowlist)}
- Denylist:
${renderList(spec.tools.denylist)}
- Non-main sandbox enabled: ${spec.tools.sandboxNonMainSessions}

## Safety Boundaries
${renderList(spec.boundaries.hardLimits)}

## Escalation Rules
${renderList(spec.boundaries.escalationRules)}
`;
}

export function renderSoulMd(spec: HarnessSpec): string {
  return `# SOUL

## Core Truths
${renderList(spec.soul.coreTruths)}

## Vibe
${spec.soul.vibe}

## Reinforcement Loop
- Enabled: ${spec.reinforcement.enabled}
- Reflection template:
${spec.reinforcement.reflectionTemplate}
`;
}

export function renderToolsMd(spec: HarnessSpec): string {
  return `# TOOLS

## Policy
- Allowlist:
${renderList(spec.tools.allowlist)}
- Denylist:
${renderList(spec.tools.denylist)}
- Sandbox non-main sessions: ${spec.tools.sandboxNonMainSessions}

## Secret Handling
- Allowed in workspace:
${renderList(spec.secrets.allowedInWorkspace)}
- Redaction rules:
${renderList(spec.secrets.redactionRules)}

## Supermemory
- Enabled: ${spec.supermemory.enabled}
- API env key: ${spec.supermemory.apiKeyEnv}
- Base URL: ${spec.supermemory.baseUrl}
- topK: ${spec.supermemory.topK}
- threshold: ${spec.supermemory.threshold}
`;
}

export function renderUserMd(spec: HarnessSpec): string {
  return `# USER

This workspace is generated for tenant "${spec.tenant.displayName}".

## Communication Style
${spec.identity.communicationStyle ?? "direct, concise, practical"}

## Coordination
- Mission Control enabled: ${spec.coordination.missionControlEnabled}
- Update channel: ${spec.updates.channel}
`;
}

export function renderHeartbeatMd(spec: HarnessSpec): string {
  return `# HEARTBEAT

## Monitoring
- Heartbeat interval (seconds): ${spec.observability.heartbeatIntervalSeconds}
- Down alert threshold (seconds): ${spec.observability.downAlertThresholdSeconds}

## Alert Targets
- Owner webhook: ${spec.observability.ownerWebhookUrl ?? "not configured"}
- Management webhook: ${spec.observability.managementWebhookUrl ?? "not configured"}
`;
}

export function renderMemoryMd(spec: HarnessSpec): string {
  return `# MEMORY

${spec.workspace.memorySeed ?? "No seed memory provided."}
`;
}

export function buildWorkspaceFiles(spec: HarnessSpec): Record<string, string> {
  const files: Record<string, string> = {
    "AGENTS.md": renderAgentsMd(spec),
    "SOUL.md": renderSoulMd(spec),
    "TOOLS.md": renderToolsMd(spec),
    "USER.md": renderUserMd(spec),
    "HEARTBEAT.md": renderHeartbeatMd(spec),
  };
  if (spec.workspace.includeMemorySeed) {
    files["MEMORY.md"] = renderMemoryMd(spec);
  }
  return files;
}
