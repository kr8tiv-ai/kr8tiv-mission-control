import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { describe, expect, test } from "vitest";

import { buildComposeTemplate } from "../src/generators/compose";
import { compileFromSpec, writeArtifacts } from "../src/harness/compiler";
import { loadHarnessFromFile } from "../src/harness/schema";

const FIXTURES_DIR = path.join(__dirname, "fixtures");
const GOLDEN_DIR = path.join(__dirname, "golden");

function readText(filePath: string): string {
  return fs.readFileSync(filePath, "utf-8").replace(/\r\n/g, "\n").trimEnd();
}

describe("harness compiler golden outputs", () => {
  test("compiles deterministic outputs that match golden files", () => {
    const spec = loadHarnessFromFile(path.join(FIXTURES_DIR, "harness.valid.yaml"));
    const tenantId = "acme-support-1234abcd";
    const artifacts = compileFromSpec(spec, tenantId);

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "kr8tiv-claw-golden-"));
    writeArtifacts(tmpDir, artifacts);
    fs.writeFileSync(
      path.join(tmpDir, "docker-compose.tenant.yml"),
      buildComposeTemplate(spec, {
        tenantId,
        containerTag: artifacts.containerTag,
        includeWatchdog: true,
      }),
      "utf-8",
    );

    const textFiles: Array<[string, string]> = [
      ["workspace/AGENTS.md", "workspace/AGENTS.md"],
      ["workspace/SOUL.md", "workspace/SOUL.md"],
      ["workspace/TOOLS.md", "workspace/TOOLS.md"],
      ["workspace/USER.md", "workspace/USER.md"],
      ["workspace/HEARTBEAT.md", "workspace/HEARTBEAT.md"],
      ["workspace/MEMORY.md", "workspace/MEMORY.md"],
      ["docker-compose.tenant.yml", "docker-compose.tenant.yml"],
    ];

    for (const [actualRel, goldenRel] of textFiles) {
      const actual = readText(path.join(tmpDir, actualRel));
      const expected = readText(path.join(GOLDEN_DIR, goldenRel));
      expect(actual).toBe(expected);
    }

    const jsonFiles: Array<[string, string]> = [
      ["openclaw.json", "openclaw.json"],
      ["skill-pack-manifest.json", "skill-pack-manifest.json"],
      ["artifact-metadata.json", "artifact-metadata.json"],
    ];
    for (const [actualRel, goldenRel] of jsonFiles) {
      const actual = JSON.parse(fs.readFileSync(path.join(tmpDir, actualRel), "utf-8"));
      const expected = JSON.parse(fs.readFileSync(path.join(GOLDEN_DIR, goldenRel), "utf-8"));
      expect(actual).toEqual(expected);
    }
  });

  test("openclaw config enforces secure defaults", () => {
    const spec = loadHarnessFromFile(path.join(FIXTURES_DIR, "harness.valid.yaml"));
    const artifacts = compileFromSpec(spec, "acme-support-aaaaaaaa");
    const config = artifacts.openclawConfig as Record<string, unknown>;
    const gateway = config.gateway as Record<string, unknown>;
    const pairing = gateway.pairing as Record<string, unknown>;
    const group = gateway.group as Record<string, unknown>;
    const agents = config.agents as Record<string, unknown>;
    const defaults = agents.defaults as Record<string, unknown>;
    const sandbox = defaults.sandbox as Record<string, unknown>;

    expect(pairing.required).toBe(true);
    expect(group.mentionGating).toBe(true);
    expect(sandbox.nonMainSessions).toBe("strict");
  });
});
