import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { buildOpenclawConfig, buildSkillPackManifest } from "../generators/openclawConfig";
import { buildWorkspaceFiles } from "../generators/workspace";
import { loadHarnessFromFile } from "./schema";
import type { CompiledArtifacts, HarnessSpec } from "../types";

function ensureDir(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

function writeJson(filePath: string, payload: unknown): void {
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + "\n", "utf-8");
}

export function buildTenantId(slug: string): string {
  const normalized = slug.toLowerCase().replace(/[^a-z0-9-]/g, "-");
  const randomPart = crypto.randomBytes(4).toString("hex");
  return `${normalized}-${randomPart}`;
}

export function resolveContainerTag(spec: HarnessSpec, tenantId: string): string {
  if (spec.tenant.containerTag?.trim()) {
    return spec.tenant.containerTag.trim();
  }
  return `${spec.supermemory.containerTagPrefix}:${tenantId}`;
}

export function compileFromSpec(spec: HarnessSpec, tenantId: string): CompiledArtifacts {
  const containerTag = resolveContainerTag(spec, tenantId);
  return {
    tenantId,
    containerTag,
    workspaceFiles: buildWorkspaceFiles(spec),
    openclawConfig: buildOpenclawConfig(spec),
    skillPackManifest: buildSkillPackManifest(spec, tenantId),
  };
}

export function writeArtifacts(outDir: string, artifacts: CompiledArtifacts): void {
  ensureDir(outDir);
  const workspaceDir = path.join(outDir, "workspace");
  ensureDir(workspaceDir);
  ensureDir(path.join(workspaceDir, "skills"));

  for (const [fileName, content] of Object.entries(artifacts.workspaceFiles)) {
    fs.writeFileSync(path.join(workspaceDir, fileName), content.trimEnd() + "\n", "utf-8");
  }

  writeJson(path.join(outDir, "openclaw.json"), artifacts.openclawConfig);
  writeJson(path.join(outDir, "skill-pack-manifest.json"), artifacts.skillPackManifest);
  writeJson(path.join(outDir, "artifact-metadata.json"), {
    tenantId: artifacts.tenantId,
    containerTag: artifacts.containerTag,
    workspaceFiles: Object.keys(artifacts.workspaceFiles).sort(),
  });
}

export function compileHarness(params: {
  harnessPath: string;
  outDir: string;
  tenantSlug: string;
}): CompiledArtifacts {
  const spec = loadHarnessFromFile(params.harnessPath);
  const tenantId = buildTenantId(params.tenantSlug || spec.tenant.slug);
  const artifacts = compileFromSpec(spec, tenantId);
  writeArtifacts(params.outDir, artifacts);
  return artifacts;
}
