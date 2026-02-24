import fs from "node:fs";
import yaml from "js-yaml";
import { z } from "zod";

import type { HarnessSpec } from "../types";

const nonEmptyString = z.string().trim().min(1);

const skillPackSchema = z.object({
  name: nonEmptyString,
  source: nonEmptyString,
  version: z.string().trim().optional(),
});

const harnessSchema = z.object({
  tenant: z.object({
    slug: nonEmptyString.regex(/^[a-z0-9][a-z0-9-]*$/, "tenant.slug must be kebab-case"),
    displayName: nonEmptyString,
    containerTag: z.string().trim().optional(),
  }),
  identity: z.object({
    role: nonEmptyString,
    purpose: nonEmptyString,
    personality: nonEmptyString,
    communicationStyle: z.string().trim().optional(),
  }),
  soul: z.object({
    coreTruths: z.array(nonEmptyString).min(1),
    vibe: nonEmptyString,
  }),
  boundaries: z.object({
    hardLimits: z.array(nonEmptyString).default([]),
    escalationRules: z.array(nonEmptyString).default([]),
  }),
  jobFunctions: z.object({
    responsibilities: z.array(nonEmptyString).min(1),
    successCriteria: z.array(nonEmptyString).min(1),
  }),
  channels: z.object({
    allow: z.array(nonEmptyString).min(1),
    dmPairingRequired: z.boolean().default(true),
    mentionGating: z.boolean().default(true),
  }),
  tools: z.object({
    allowlist: z.array(nonEmptyString).default([]),
    denylist: z.array(nonEmptyString).default([]),
    sandboxNonMainSessions: z.boolean().default(true),
  }),
  workspace: z.object({
    root: z.string().trim().optional(),
    retentionDays: z.number().int().positive().default(30),
    includeMemorySeed: z.boolean().default(false),
    memorySeed: z.string().optional(),
  }),
  skills: z.object({
    packs: z.array(skillPackSchema).default([]),
  }),
  secrets: z.object({
    allowedInWorkspace: z.array(nonEmptyString).default([]),
    redactionRules: z.array(nonEmptyString).default([]),
  }),
  supermemory: z.object({
    enabled: z.boolean().default(false),
    apiKeyEnv: nonEmptyString.default("SUPERMEMORY_API_KEY"),
    baseUrl: nonEmptyString.default("https://api.supermemory.ai"),
    containerTagPrefix: nonEmptyString.default("tenant"),
    topK: z.number().int().positive().default(8),
    threshold: z.number().min(0).max(1).default(0.45),
  }),
  memoryIngestion: z.object({
    enableAutoIngestion: z.boolean().default(true),
    dedupeByCustomId: z.boolean().default(true),
    metadataNamespace: nonEmptyString.default("kr8tiv-claw"),
  }),
  reinforcement: z.object({
    enabled: z.boolean().default(true),
    reflectionTemplate: nonEmptyString.default(
      "Goal | Outcome | What worked | What failed | Rule for next time",
    ),
  }),
  observability: z.object({
    ownerWebhookUrl: z.string().url().optional(),
    managementWebhookUrl: z.string().url().optional(),
    heartbeatIntervalSeconds: z.number().int().positive().default(60),
    downAlertThresholdSeconds: z.number().int().positive().default(300),
  }),
  updates: z.object({
    channel: z.enum(["stable", "beta", "dev"]).default("stable"),
    rolloutWindow: z.string().trim().optional(),
  }),
  coordination: z.object({
    missionControlEnabled: z.boolean().default(false),
  }),
});

export function parseHarness(raw: unknown): HarnessSpec {
  return harnessSchema.parse(raw) as HarnessSpec;
}

export function loadHarnessFromFile(filePath: string): HarnessSpec {
  const content = fs.readFileSync(filePath, "utf-8");
  const parsed = yaml.load(content);
  return parseHarness(parsed);
}

export { harnessSchema };
