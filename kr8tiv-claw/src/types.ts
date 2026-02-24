export type UpdateChannel = "stable" | "beta" | "dev";

export interface SkillPackRef {
  name: string;
  source: string;
  version?: string;
}

export interface HarnessSpec {
  tenant: {
    slug: string;
    displayName: string;
    containerTag?: string;
  };
  identity: {
    role: string;
    purpose: string;
    personality: string;
    communicationStyle?: string;
  };
  soul: {
    coreTruths: string[];
    vibe: string;
  };
  boundaries: {
    hardLimits: string[];
    escalationRules: string[];
  };
  jobFunctions: {
    responsibilities: string[];
    successCriteria: string[];
  };
  channels: {
    allow: string[];
    dmPairingRequired: boolean;
    mentionGating: boolean;
  };
  tools: {
    allowlist: string[];
    denylist: string[];
    sandboxNonMainSessions: boolean;
  };
  workspace: {
    root?: string;
    retentionDays?: number;
    includeMemorySeed: boolean;
    memorySeed?: string;
  };
  skills: {
    packs: SkillPackRef[];
  };
  secrets: {
    allowedInWorkspace: string[];
    redactionRules: string[];
  };
  supermemory: {
    enabled: boolean;
    apiKeyEnv: string;
    baseUrl: string;
    containerTagPrefix: string;
    topK: number;
    threshold: number;
  };
  memoryIngestion: {
    enableAutoIngestion: boolean;
    dedupeByCustomId: boolean;
    metadataNamespace: string;
  };
  reinforcement: {
    enabled: boolean;
    reflectionTemplate: string;
  };
  observability: {
    ownerWebhookUrl?: string;
    managementWebhookUrl?: string;
    heartbeatIntervalSeconds: number;
    downAlertThresholdSeconds: number;
  };
  updates: {
    channel: UpdateChannel;
    rolloutWindow?: string;
  };
  coordination: {
    missionControlEnabled: boolean;
  };
}

export interface CompiledArtifacts {
  tenantId: string;
  containerTag: string;
  workspaceFiles: Record<string, string>;
  openclawConfig: Record<string, unknown>;
  skillPackManifest: Record<string, unknown>;
}
