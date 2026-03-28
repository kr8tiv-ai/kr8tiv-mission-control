import { describe, expect, it } from 'vitest';
import { parseHarness } from '../src/compiler/schema.js';

describe('harness schema validation', () => {
  it('accepts minimal valid config', () => {
    const parsed = parseHarness({
      tenantId: 't1',
      name: 'Agent',
      role: 'Role',
      soul: { truths: ['truth'], voice: 'voice' },
      jobFunctions: ['do thing']
    });

    expect(parsed.channels.dmPairingRequired).toBe(true);
    expect(parsed.sandbox.nonMainSessionsIsolated).toBe(true);
    expect(parsed.modelPolicy.primary).toBe('openai-codex/gpt-5.3-codex');
    expect(parsed.modelPolicy.lockRoutes).toBe(true);
    expect(parsed.reasoningPolicy.default).toBe('max');
    expect(parsed.reasoningPolicy.fallbackBehavior).toBe('highest_or_model_default');
    expect(parsed.persona.presetRef).toBeDefined();
    expect(parsed.persona.mode).toBe('team');
    expect(parsed.onboarding.recommendationEnabled).toBe(true);
    expect(parsed.onboarding.personalizedDefaults).toContain('voice');
    expect(parsed.onboarding.personalizedDefaults).toContain('uplay_chromium');
    expect(parsed.recovery.teamOrder).toEqual(['FRIDAY', 'ARSENAL', 'JOCASTA', 'EDITH']);
    expect(parsed.controlPlane.missionControlUrl).toBe('http://mission-control:8000');
    expect(parsed.controlPlane.telemetry.enabled).toBe(true);
    expect(parsed.controlPlane.privacy.crossTenantLearning).toBe(false);
    expect(parsed.controlPlane.privacy.crossUserLearning).toBe(false);
  });

  it('rejects invalid watchdog URL when enabled', () => {
    expect(() =>
      parseHarness({
        tenantId: 't1',
        name: 'Agent',
        role: 'Role',
        soul: { truths: ['truth'], voice: 'voice' },
        jobFunctions: ['do thing'],
        watchdog: { enabled: true, webhookUrl: 'not-a-url', intervalSeconds: 60 }
      })
    ).toThrowError();
  });

  it('rejects missing watchdog URL when enabled', () => {
    expect(() =>
      parseHarness({
        tenantId: 't1',
        name: 'Agent',
        role: 'Role',
        soul: { truths: ['truth'], voice: 'voice' },
        jobFunctions: ['do thing'],
        watchdog: { enabled: true, intervalSeconds: 60 }
      })
    ).toThrowError(/watchdog.webhookUrl/);
  });

  it('rejects supermemory enabled without containerTag', () => {
    expect(() =>
      parseHarness({
        tenantId: 't1',
        name: 'Agent',
        role: 'Role',
        soul: { truths: ['truth'], voice: 'voice' },
        jobFunctions: ['do thing'],
        memory: { supermemory: { enabled: true } }
      })
    ).toThrowError(/containerTag/);
  });

  it('rejects tool allow/deny overlap', () => {
    expect(() =>
      parseHarness({
        tenantId: 't1',
        name: 'Agent',
        role: 'Role',
        soul: { truths: ['truth'], voice: 'voice' },
        jobFunctions: ['do thing'],
        tooling: { allow: ['shell.exec'], deny: ['shell.exec'] }
      })
    ).toThrowError(/overlap/);
  });

  it('rejects unsafe tenant/container tags', () => {
    expect(() =>
      parseHarness({
        tenantId: 'Bad Tenant',
        name: 'Agent',
        role: 'Role',
        soul: { truths: ['truth'], voice: 'voice' },
        jobFunctions: ['do thing']
      })
    ).toThrowError(/kebab-case/);

    expect(() =>
      parseHarness({
        tenantId: 'good-tenant',
        name: 'Agent',
        role: 'Role',
        soul: { truths: ['truth'], voice: 'voice' },
        jobFunctions: ['do thing'],
        memory: { supermemory: { enabled: true, containerTag: 'Bad Tag' } }
      })
    ).toThrowError(/kebab-case/);
  });

  it('rejects duplicate recovery team order entries', () => {
    expect(() =>
      parseHarness({
        tenantId: 't1',
        name: 'Agent',
        role: 'Role',
        soul: { truths: ['truth'], voice: 'voice' },
        jobFunctions: ['do thing'],
        recovery: { teamOrder: ['FRIDAY', 'FRIDAY'], singleOwner: true, cooldownSeconds: 300 }
      })
    ).toThrowError(/must not contain duplicates/);
  });

  it('rejects invalid controlPlane.packRef format', () => {
    expect(() =>
      parseHarness({
        tenantId: 't1',
        name: 'Agent',
        role: 'Role',
        soul: { truths: ['truth'], voice: 'voice' },
        jobFunctions: ['do thing'],
        controlPlane: {
          missionControlUrl: 'http://mission-control:8000',
          missionControlTokenFile: '/run/secrets/mission_control_token',
          tier: 'personal',
          packRef: 'invalid-pack-ref',
          telemetry: { enabled: true },
          privacy: {
            crossTenantLearning: false,
            crossUserLearning: false
          }
        }
      })
    ).toThrowError(/packRef/);
  });
});
