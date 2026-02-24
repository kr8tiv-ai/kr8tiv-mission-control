import fs from "node:fs";
import path from "node:path";

import { buildComposeTemplate } from "./generators/compose";
import { compileFromSpec, compileHarness, writeArtifacts } from "./harness/compiler";
import { loadHarnessFromFile } from "./harness/schema";

interface ParsedArgs {
  command: string;
  flags: Record<string, string | boolean>;
}

function parseArgs(argv: string[]): ParsedArgs {
  const [command = "", ...rest] = argv;
  const flags: Record<string, string | boolean> = {};
  for (let i = 0; i < rest.length; i += 1) {
    const token = rest[i];
    if (!token.startsWith("--")) {
      continue;
    }
    const key = token.slice(2);
    const next = rest[i + 1];
    if (!next || next.startsWith("--")) {
      flags[key] = true;
      continue;
    }
    flags[key] = next;
    i += 1;
  }
  return { command, flags };
}

function requiredString(flags: Record<string, string | boolean>, key: string): string {
  const value = flags[key];
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Missing required --${key}`);
  }
  return value.trim();
}

async function runCompile(flags: Record<string, string | boolean>): Promise<void> {
  const harnessPath = requiredString(flags, "harness");
  const outDir = requiredString(flags, "out");
  const tenant = requiredString(flags, "tenant");
  const tenantIdFlag =
    typeof flags["tenant-id"] === "string" && flags["tenant-id"].trim()
      ? flags["tenant-id"].trim()
      : null;
  const artifacts = tenantIdFlag
    ? (() => {
        const spec = loadHarnessFromFile(harnessPath);
        const compiled = compileFromSpec(spec, tenantIdFlag);
        writeArtifacts(outDir, compiled);
        return compiled;
      })()
    : compileHarness({
        harnessPath,
        outDir,
        tenantSlug: tenant,
      });
  process.stdout.write(
    JSON.stringify({ ok: true, tenantId: artifacts.tenantId, outDir }, null, 2) + "\n",
  );
}

async function runCompose(flags: Record<string, string | boolean>): Promise<void> {
  const harnessPath = requiredString(flags, "harness");
  const outDir = requiredString(flags, "out");
  const tenant = requiredString(flags, "tenant");
  const includeWatchdog = Boolean(flags.watchdog);

  const spec = loadHarnessFromFile(harnessPath);
  const artifacts = compileFromSpec(spec, tenant);
  writeArtifacts(outDir, artifacts);
  const composeText = buildComposeTemplate(spec, {
    tenantId: artifacts.tenantId,
    containerTag: artifacts.containerTag,
    includeWatchdog,
  });
  fs.writeFileSync(path.join(outDir, "docker-compose.tenant.yml"), composeText, "utf-8");
  process.stdout.write(
    JSON.stringify(
      {
        ok: true,
        tenantId: artifacts.tenantId,
        outDir,
        includeWatchdog,
      },
      null,
      2,
    ) + "\n",
  );
}

async function runHealth(flags: Record<string, string | boolean>): Promise<void> {
  const tokenFlag = flags.token;
  const token =
    typeof tokenFlag === "string" && tokenFlag.trim()
      ? tokenFlag.trim()
      : process.env.OPENCLAW_GATEWAY_TOKEN ?? "";
  const configPath =
    typeof flags.config === "string" && flags.config.trim() ? flags.config.trim() : "";

  if (!token || token.length < 16) {
    process.stderr.write("health: OPENCLAW_GATEWAY_TOKEN missing or too short\n");
    throw new Error("invalid health token");
  }
  if (configPath) {
    if (!fs.existsSync(configPath)) {
      process.stderr.write(`health: config path missing (${configPath})\n`);
      throw new Error("missing config path");
    }
    try {
      JSON.parse(fs.readFileSync(configPath, "utf-8"));
    } catch (error) {
      process.stderr.write(`health: invalid config json (${String(error)})\n`);
      throw new Error("invalid config json");
    }
  }
  process.stdout.write("health:ok\n");
}

async function postWebhook(
  url: string | undefined,
  payload: Record<string, unknown>,
): Promise<void> {
  if (!url) {
    return;
  }
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // Best-effort heartbeat pings only.
  }
}

async function runWatchdog(flags: Record<string, string | boolean>): Promise<void> {
  const tenant = requiredString(flags, "tenant");
  const ownerWebhook =
    typeof flags["owner-webhook"] === "string"
      ? flags["owner-webhook"].trim()
      : process.env.OWNER_WEBHOOK_URL;
  const managementWebhook =
    typeof flags["management-webhook"] === "string"
      ? flags["management-webhook"].trim()
      : process.env.MANAGEMENT_WEBHOOK_URL;
  const intervalRaw =
    typeof flags["interval-seconds"] === "string" ? flags["interval-seconds"] : "60";
  const intervalSeconds = Number.parseInt(intervalRaw, 10);
  const intervalMs =
    Number.isFinite(intervalSeconds) && intervalSeconds > 0 ? intervalSeconds * 1000 : 60_000;

  while (true) {
    const payload = {
      tenant,
      status: "alive",
      timestamp: new Date().toISOString(),
    };
    await postWebhook(ownerWebhook, payload);
    await postWebhook(managementWebhook, payload);
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export async function runCli(argv: string[]): Promise<number> {
  try {
    const { command, flags } = parseArgs(argv);
    switch (command) {
      case "compile":
        await runCompile(flags);
        return 0;
      case "compose":
        await runCompose(flags);
        return 0;
      case "health":
        await runHealth(flags);
        return 0;
      case "watchdog":
        await runWatchdog(flags);
        return 0;
      default:
        process.stderr.write(
          "Usage: node dist/index.js <compile|compose|health|watchdog> [--flags]\n",
        );
        return 2;
    }
  } catch (error: unknown) {
    process.stderr.write(`kr8tiv-claw error: ${String(error)}\n`);
    return 1;
  }
}
