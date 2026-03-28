import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { loadHarnessFromYaml, compileHarness } from '../src/compiler/harness-compiler.js';
import { generateTenantCompose } from '../src/compiler/compose-generator.js';

const fixtureRoot = path.join(process.cwd(), 'tests/fixtures');
const goldenRoot = path.join(fixtureRoot, 'golden');

function normalizeEol(value: string): string {
  return value.replace(/\r\n/g, '\n');
}

function readGolden(file: string): string {
  return normalizeEol(readFileSync(path.join(goldenRoot, file), 'utf8'));
}

describe('harness compiler golden outputs', () => {
  it('matches workspace and config artifacts', async () => {
    const cfg = await loadHarnessFromYaml(path.join(fixtureRoot, 'harness.yaml'));
    const artifacts = compileHarness(cfg);
    const byName = new Map(artifacts.map((a) => [a.path, a.content]));

    for (const file of [
      'AGENTS.md',
      'SOUL.md',
      'TOOLS.md',
      'USER.md',
      'HEARTBEAT.md',
      'TASKS.md',
      '.env.example',
      'MEMORY.md',
      'openclaw.json',
      'skill-pack.manifest.json'
    ]) {
      expect(normalizeEol(byName.get(file) ?? '')).toBe(readGolden(file));
    }
  });

  it('matches compose template', async () => {
    const cfg = await loadHarnessFromYaml(path.join(fixtureRoot, 'harness.yaml'));
    expect(normalizeEol(generateTenantCompose(cfg))).toBe(readGolden('docker-compose.yml'));
  });
});
