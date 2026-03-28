import { z } from 'zod';

/**
 * 15-point harness schema that compiles to OpenClaw workspace/config artifacts.
 * Keep this as the single source of truth for distribution-level behavior.
 */
export const HarnessSchema = z
  .object({
    tenantId: z.string().min(1).regex(/^[a-z0-9][a-z0-9-]*$/, 'tenantId must be kebab-case safe'),
    name: z.string().min(1),
    role: z.string().min(1),
    soul: z.object({
      truths: z.array(z.string().min(1)).min(1),
      voice: z.string().min(1),
      boundaries: z.array(z.string().min(1)).default([])
    }),
    jobFunctions: z.array(z.string().min(1)).min(1),
    channels: z
      .object({
        whatsapp: z.boolean().default(false),
        telegram: z.boolean().default(false),
        dmPairingRequired: z.boolean().default(true),
        mentionGating: z.boolean().default(true)
      })
      .default({}),
    tooling: z
      .object({
        allow: z.array(z.string().min(1)).default([]),
        deny: z.array(z.string().min(1)).default([]),
        elevatedMode: z.boolean().default(false)
      })
      .default({}),
    sandbox: z
      .object({
        nonMainSessionsIsolated: z.boolean().default(true)
      })
      .default({}),
    memory: z
      .object({
        seed: z.array(z.string().min(1)).optional(),
        retentionPolicy: z.string().min(1).default('local-first'),
        supermemory: z
          .object({
            enabled: z.boolean().default(false),
            containerTag: z.string().min(1).optional()
          })
          .default({ enabled: false })
      })
      .default({}),
    updateRing: z.enum(['stable', 'beta', 'dev']).default('stable'),
    watchdog: z
      .object({
        enabled: z.boolean().default(false),
        webhookUrl: z.string().url().optional(),
        intervalSeconds: z.number().int().min(30).default(60)
      })
      .default({ enabled: false, intervalSeconds: 60 }),
    skills: z
      .object({
        workspace: z.array(z.string().min(1)).default([])
      })
      .default({ workspace: [] }),
    openclaw: z
      .object({
        image: z.string().min(1).default('ghcr.io/openclaw/openclaw:latest')
      })
      .default({ image: 'ghcr.io/openclaw/openclaw:latest' }),
    modelPolicy: z
      .object({
        primary: z.string().min(1).default('openai-codex/gpt-5.3-codex'),
        fallbacks: z.array(z.string().min(1)).default([]),
        lockRoutes: z.boolean().default(true),
        allowRuntimeOverride: z.boolean().default(false),
        fallbackOn: z
          .array(
            z.enum(['rate_limit', 'provider_cooldown', 'billing_disabled', 'auth_profile_unavailable'])
          )
          .default(['rate_limit', 'provider_cooldown', 'billing_disabled', 'auth_profile_unavailable'])
      })
      .default({
        primary: 'openai-codex/gpt-5.3-codex',
        fallbacks: [],
        lockRoutes: true,
        allowRuntimeOverride: false,
        fallbackOn: ['rate_limit', 'provider_cooldown', 'billing_disabled', 'auth_profile_unavailable']
      }),
    reasoningPolicy: z
      .object({
        default: z.enum(['max', 'high', 'normal', 'off']).default('max'),
        fallbackBehavior: z
          .enum(['highest_or_model_default', 'model_default'])
          .default('highest_or_model_default')
      })
      .default({
        default: 'max',
        fallbackBehavior: 'highest_or_model_default'
      }),
    persona: z
      .object({
        presetRef: z.string().min(1).default('default-team'),
        mode: z.enum(['team', 'individual']).default('team'),
        orchestratorEnabled: z.boolean().default(true)
      })
      .default({
        presetRef: 'default-team',
        mode: 'team',
        orchestratorEnabled: true
      }),
    onboarding: z
      .object({
        recommendationEnabled: z.boolean().default(true),
        personalizedDefaults: z
          .array(z.enum(['voice', 'uplay_chromium', 'mission_control_tasks', 'notebooklm']))
          .default(['voice', 'uplay_chromium']),
        autoNotebooklmPrompt: z.boolean().default(true)
      })
      .default({
        recommendationEnabled: true,
        personalizedDefaults: ['voice', 'uplay_chromium'],
        autoNotebooklmPrompt: true
      }),
    recovery: z
      .object({
        teamOrder: z
          .array(z.enum(['FRIDAY', 'ARSENAL', 'JOCASTA', 'EDITH']))
          .default(['FRIDAY', 'ARSENAL', 'JOCASTA', 'EDITH']),
        singleOwner: z.boolean().default(true),
        cooldownSeconds: z.number().int().min(30).default(300)
      })
      .default({
        teamOrder: ['FRIDAY', 'ARSENAL', 'JOCASTA', 'EDITH'],
        singleOwner: true,
        cooldownSeconds: 300
      }),
    controlPlane: z
      .object({
        missionControlUrl: z.string().url().default('http://mission-control:8000'),
        missionControlTokenFile: z.string().min(1).default('/run/secrets/mission_control_token'),
        tier: z.enum(['personal', 'enterprise']).default('personal'),
        packRef: z.string().min(1).default('engineering-delivery-pack@1'),
        telemetry: z
          .object({
            enabled: z.boolean().default(true)
          })
          .default({ enabled: true }),
        privacy: z
          .object({
            crossTenantLearning: z.boolean().default(false),
            crossUserLearning: z.boolean().default(false)
          })
          .default({
            crossTenantLearning: false,
            crossUserLearning: false
          })
      })
      .default({
        missionControlUrl: 'http://mission-control:8000',
        missionControlTokenFile: '/run/secrets/mission_control_token',
        tier: 'personal',
        packRef: 'engineering-delivery-pack@1',
        telemetry: { enabled: true },
        privacy: {
          crossTenantLearning: false,
          crossUserLearning: false
        }
      })
  })
  .superRefine((data, ctx) => {
    if (data.watchdog.enabled && !data.watchdog.webhookUrl) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['watchdog', 'webhookUrl'],
        message: 'watchdog.webhookUrl is required when watchdog.enabled is true'
      });
    }

    if (data.memory.supermemory.enabled && !data.memory.supermemory.containerTag) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['memory', 'supermemory', 'containerTag'],
        message: 'memory.supermemory.containerTag is required when supermemory is enabled'
      });
    }

    const allow = new Set(data.tooling.allow);
    const overlap = data.tooling.deny.filter((entry) => allow.has(entry));
    if (overlap.length > 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['tooling'],
        message: `tooling.allow and tooling.deny overlap: ${overlap.join(', ')}`
      });
    }

    if (data.memory.supermemory.containerTag && !/^[a-z0-9][a-z0-9-]*$/.test(data.memory.supermemory.containerTag)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['memory', 'supermemory', 'containerTag'],
        message: 'containerTag must be kebab-case safe'
      });
    }

    if (!data.recovery.teamOrder.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['recovery', 'teamOrder'],
        message: 'recovery.teamOrder must include at least one agent'
      });
    }

    const recoveryOrder = new Set(data.recovery.teamOrder);
    if (recoveryOrder.size !== data.recovery.teamOrder.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['recovery', 'teamOrder'],
        message: 'recovery.teamOrder must not contain duplicates'
      });
    }

    if (!/^[a-z0-9][a-z0-9-]*@[0-9]+$/.test(data.controlPlane.packRef)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['controlPlane', 'packRef'],
        message: 'controlPlane.packRef must be formatted as <pack-key>@<version>'
      });
    }

    if (data.persona.mode === 'individual' && data.persona.orchestratorEnabled) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['persona', 'orchestratorEnabled'],
        message: 'persona.orchestratorEnabled must be false when persona.mode is individual'
      });
    }
  });

export type HarnessConfig = z.infer<typeof HarnessSchema>;

export function parseHarness(raw: unknown): HarnessConfig {
  return HarnessSchema.parse(raw);
}

export function getHarnessJsonShape(): Record<string, unknown> {
  return {
    type: 'object',
    required: ['tenantId', 'name', 'role', 'soul', 'jobFunctions'],
    properties: {
      tenantId: { type: 'string', pattern: '^[a-z0-9][a-z0-9-]*$' },
      name: { type: 'string' },
      role: { type: 'string' },
      soul: {
        type: 'object',
        required: ['truths', 'voice'],
        properties: {
          truths: { type: 'array', items: { type: 'string' }, minItems: 1 },
          voice: { type: 'string' },
          boundaries: { type: 'array', items: { type: 'string' } }
        }
      },
      jobFunctions: { type: 'array', items: { type: 'string' }, minItems: 1 },
      modelPolicy: {
        type: 'object',
        properties: {
          primary: { type: 'string' },
          fallbacks: { type: 'array', items: { type: 'string' } },
          lockRoutes: { type: 'boolean' },
          allowRuntimeOverride: { type: 'boolean' },
          fallbackOn: { type: 'array', items: { type: 'string' } }
        }
      },
      reasoningPolicy: {
        type: 'object',
        properties: {
          default: { type: 'string', enum: ['max', 'high', 'normal', 'off'] },
          fallbackBehavior: { type: 'string', enum: ['highest_or_model_default', 'model_default'] }
        }
      },
      persona: {
        type: 'object',
        properties: {
          presetRef: { type: 'string' },
          mode: { type: 'string', enum: ['team', 'individual'] },
          orchestratorEnabled: { type: 'boolean' }
        }
      },
      onboarding: {
        type: 'object',
        properties: {
          recommendationEnabled: { type: 'boolean' },
          personalizedDefaults: { type: 'array', items: { type: 'string' } },
          autoNotebooklmPrompt: { type: 'boolean' }
        }
      },
      recovery: {
        type: 'object',
        properties: {
          teamOrder: { type: 'array', items: { type: 'string' } },
          singleOwner: { type: 'boolean' },
          cooldownSeconds: { type: 'number' }
        }
      },
      controlPlane: {
        type: 'object',
        properties: {
          missionControlUrl: { type: 'string' },
          missionControlTokenFile: { type: 'string' },
          tier: { type: 'string', enum: ['personal', 'enterprise'] },
          packRef: { type: 'string' },
          telemetry: {
            type: 'object',
            properties: {
              enabled: { type: 'boolean' }
            }
          },
          privacy: {
            type: 'object',
            properties: {
              crossTenantLearning: { type: 'boolean' },
              crossUserLearning: { type: 'boolean' }
            }
          }
        }
      }
    }
  };
}
