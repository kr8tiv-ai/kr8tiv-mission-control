import path from 'node:path';
import { promises as fs } from 'node:fs';
import YAML from 'yaml';
import { parseHarness, type HarnessConfig } from './schema.js';
import {
  renderAgentsMd,
  renderEnvExample,
  renderHeartbeatMd,
  renderMemoryMd,
  renderSoulMd,
  renderTasksMd,
  renderToolsMd,
  renderUserMd
} from '../templates/workspace.js';

export type CompiledArtifact = { path: string; content: string };

export async function loadHarnessFromYaml(filePath: string): Promise<HarnessConfig> {
  const raw = await fs.readFile(filePath, 'utf8');
  const parsed = YAML.parse(raw);
  return parseHarness(parsed);
}

/**
 * Distribution-level OpenClaw config output.
 * Keeps defaults secure for messaging surfaces.
 */
export function buildOpenClawConfig(cfg: HarnessConfig): Record<string, unknown> {
  return {
    tenantId: cfg.tenantId,
    updateRing: cfg.updateRing,
    security: {
      pairing: cfg.channels.dmPairingRequired,
      mentionGating: cfg.channels.mentionGating,
      sandboxNonMainSessions: cfg.sandbox.nonMainSessionsIsolated,
      toolAllowList: cfg.tooling.allow,
      toolDenyList: cfg.tooling.deny,
      elevatedMode: cfg.tooling.elevatedMode
    },
    channels: {
      whatsapp: cfg.channels.whatsapp,
      telegram: cfg.channels.telegram
    },
    memory: {
      retentionPolicy: cfg.memory.retentionPolicy,
      supermemory: cfg.memory.supermemory
    },
    modelPolicy: {
      primary: cfg.modelPolicy.primary,
      fallbacks: cfg.modelPolicy.fallbacks,
      lockRoutes: cfg.modelPolicy.lockRoutes,
      allowRuntimeOverride: cfg.modelPolicy.allowRuntimeOverride,
      fallbackOn: cfg.modelPolicy.fallbackOn
    },
    reasoningPolicy: {
      default: cfg.reasoningPolicy.default,
      fallbackBehavior: cfg.reasoningPolicy.fallbackBehavior
    },
    persona: {
      presetRef: cfg.persona.presetRef,
      mode: cfg.persona.mode,
      orchestratorEnabled: cfg.persona.orchestratorEnabled
    },
    onboarding: {
      recommendationEnabled: cfg.onboarding.recommendationEnabled,
      personalizedDefaults: cfg.onboarding.personalizedDefaults,
      autoNotebooklmPrompt: cfg.onboarding.autoNotebooklmPrompt
    },
    recovery: {
      teamOrder: cfg.recovery.teamOrder,
      singleOwner: cfg.recovery.singleOwner,
      cooldownSeconds: cfg.recovery.cooldownSeconds
    },
    controlPlane: {
      missionControlManaged: true,
      allowSelfMutation: false,
      missionControlUrl: cfg.controlPlane.missionControlUrl,
      missionControlTokenFile: cfg.controlPlane.missionControlTokenFile,
      tier: cfg.controlPlane.tier,
      packRef: cfg.controlPlane.packRef,
      telemetry: {
        enabled: cfg.controlPlane.telemetry.enabled
      },
      privacy: {
        crossTenantLearning: cfg.controlPlane.privacy.crossTenantLearning,
        crossUserLearning: cfg.controlPlane.privacy.crossUserLearning
      }
    },
    distribution: {
      generatedBy: 'kr8tiv-claw-harness-compiler'
    }
  };
}

export function buildSkillPackManifest(cfg: HarnessConfig): Record<string, unknown> {
  return {
    version: 1,
    installRoot: '<workspace>/skills',
    installMode: 'copy',
    skills: cfg.skills.workspace.map((source) => ({
      source,
      destination: path.posix.join('<workspace>/skills', path.posix.basename(source))
    }))
  };
}

export function compileHarness(cfg: HarnessConfig): CompiledArtifact[] {
  const files: CompiledArtifact[] = [
    { path: 'AGENTS.md', content: renderAgentsMd(cfg) },
    { path: 'SOUL.md', content: renderSoulMd(cfg) },
    { path: 'TOOLS.md', content: renderToolsMd(cfg) },
    { path: 'USER.md', content: renderUserMd(cfg) },
    { path: 'HEARTBEAT.md', content: renderHeartbeatMd(cfg) },
    { path: 'TASKS.md', content: renderTasksMd(cfg) },
    { path: '.env.example', content: renderEnvExample(cfg) },
    { path: 'openclaw.json', content: `${JSON.stringify(buildOpenClawConfig(cfg), null, 2)}\n` },
    { path: 'skill-pack.manifest.json', content: `${JSON.stringify(buildSkillPackManifest(cfg), null, 2)}\n` }
  ];

  const memory = renderMemoryMd(cfg);
  if (memory) files.push({ path: 'MEMORY.md', content: memory });

  return files;
}

export async function writeCompiledHarness(outputDir: string, artifacts: CompiledArtifact[]): Promise<void> {
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(
    artifacts.map(async (artifact) => {
      const target = path.join(outputDir, artifact.path);
      await fs.mkdir(path.dirname(target), { recursive: true });
      const temp = `${target}.tmp`;
      await fs.writeFile(temp, artifact.content, 'utf8');
      await fs.rename(temp, target);
    })
  );
}
