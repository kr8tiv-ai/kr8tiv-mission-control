#!/usr/bin/env node
import path from 'node:path';
import { promises as fs } from 'node:fs';
import {
  loadHarnessFromYaml,
  compileHarness,
  writeCompiledHarness
} from '../compiler/harness-compiler.js';
import { generateTenantCompose } from '../compiler/compose-generator.js';
import { getHarnessJsonShape } from '../compiler/schema.js';

function readFlag(name: string): string | undefined {
  const idx = process.argv.indexOf(name);
  if (idx === -1) return undefined;
  return process.argv[idx + 1];
}

function hasFlag(name: string): boolean {
  return process.argv.includes(name);
}

type Command = 'compile' | 'compose' | 'validate' | 'schema';

function command(): Command {
  if (hasFlag('--schema')) return 'schema';
  if (hasFlag('--validate')) return 'validate';
  if (hasFlag('--compose-only')) return 'compose';
  return 'compile';
}

async function main(): Promise<void> {
  const input = readFlag('--input') ?? 'harness.yaml';
  const output = readFlag('--output') ?? 'out';
  const composeOut = readFlag('--compose-out') ?? path.join(output, 'docker-compose.yml');

  const cmd = command();

  if (cmd === 'schema') {
    // eslint-disable-next-line no-console
    console.log(JSON.stringify(getHarnessJsonShape(), null, 2));
    return;
  }

  const cfg = await loadHarnessFromYaml(input);

  if (cmd === 'validate') {
    // eslint-disable-next-line no-console
    console.log(`Harness is valid: ${input}`);
    return;
  }

  if (cmd === 'compile') {
    const artifacts = compileHarness(cfg);
    await writeCompiledHarness(output, artifacts);

    const compose = generateTenantCompose(cfg);
    await fs.mkdir(path.dirname(composeOut), { recursive: true });
    await fs.writeFile(composeOut, compose, 'utf8');

    // eslint-disable-next-line no-console
    console.log(`Compiled ${artifacts.length + 1} files to ${output}`);
    return;
  }

  const compose = generateTenantCompose(cfg);
  await fs.mkdir(path.dirname(composeOut), { recursive: true });
  await fs.writeFile(composeOut, compose, 'utf8');
  // eslint-disable-next-line no-console
  console.log(`Generated compose file at ${composeOut}`);
}

main().catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error);
  process.exit(1);
});
