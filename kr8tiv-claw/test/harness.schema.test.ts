import path from "node:path";

import { describe, expect, test } from "vitest";

import { loadHarnessFromFile, parseHarness } from "../src/harness/schema";

const FIXTURES_DIR = path.join(__dirname, "fixtures");

describe("harness schema", () => {
  test("loads a valid harness fixture", () => {
    const spec = loadHarnessFromFile(path.join(FIXTURES_DIR, "harness.valid.yaml"));
    expect(spec.tenant.slug).toBe("acme-support");
    expect(spec.observability.ownerWebhookUrl).toBe("https://hooks.example.com/owner");
  });

  test("rejects invalid tenant slug", () => {
    const invalid = {
      tenant: { slug: "Not Valid", displayName: "Acme" },
    };
    expect(() => parseHarness(invalid)).toThrow(/tenant\.slug/);
  });

  test("applies defaults for optional sections", () => {
    const minimal = {
      tenant: { slug: "x-team", displayName: "X Team" },
      identity: { role: "Agent", purpose: "Assist", personality: "Direct" },
      soul: { coreTruths: ["Keep data safe"], vibe: "Focused" },
      boundaries: {},
      jobFunctions: {
        responsibilities: ["Do work"],
        successCriteria: ["Done"],
      },
      channels: { allow: ["telegram"] },
      tools: {},
      workspace: {},
      skills: {},
      secrets: {},
      supermemory: {},
      memoryIngestion: {},
      reinforcement: {},
      observability: {},
      updates: {},
      coordination: {},
    };

    const parsed = parseHarness(minimal);
    expect(parsed.channels.dmPairingRequired).toBe(true);
    expect(parsed.channels.mentionGating).toBe(true);
    expect(parsed.tools.sandboxNonMainSessions).toBe(true);
    expect(parsed.updates.channel).toBe("stable");
    expect(parsed.workspace.includeMemorySeed).toBe(false);
    expect(parsed.skills.packs).toEqual([]);
  });

  test("fails with actionable validation details for missing required sections", () => {
    expect(() =>
      parseHarness({
        tenant: { slug: "acme", displayName: "Acme" },
        identity: { role: "Agent", purpose: "Assist", personality: "Direct" },
      }),
    ).toThrow(/soul/);
  });
});
