#!/usr/bin/env node

import { runCli } from "./cli";

export * from "./types";
export * from "./harness/schema";
export * from "./harness/compiler";
export * from "./generators/compose";
export * from "./generators/openclawConfig";
export * from "./generators/workspace";
export * from "./supermemory/client";
export * from "./supermemory/conventions";
export * from "./supermemory/retrieval";

void runCli(process.argv.slice(2)).then((code) => {
  process.exit(code);
});
