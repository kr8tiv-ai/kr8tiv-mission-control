import { SupermemoryClient } from "./client";

export interface RetrievalRequest {
  query: string;
  containerTag: string;
  threshold: number;
  topK: number;
  userId?: string;
}

export async function retrieveHybridContext(
  client: SupermemoryClient,
  request: RetrievalRequest,
): Promise<string[]> {
  const payload = await client.search({
    query: request.query,
    containerTag: request.containerTag,
    threshold: request.threshold,
    topK: request.topK,
    userId: request.userId,
  });

  const rawResults = (payload.results ?? payload.items ?? payload.data ?? []) as unknown;
  if (!Array.isArray(rawResults)) {
    return [];
  }

  const deduped: string[] = [];
  const seen = new Set<string>();
  for (const item of rawResults) {
    if (typeof item !== "object" || item === null) {
      continue;
    }
    const maybeText =
      (item as Record<string, unknown>).content ??
      (item as Record<string, unknown>).text ??
      (item as Record<string, unknown>).snippet;
    if (typeof maybeText !== "string") {
      continue;
    }
    const compact = maybeText.trim().replace(/\s+/g, " ");
    if (!compact || seen.has(compact)) {
      continue;
    }
    seen.add(compact);
    deduped.push(compact);
    if (deduped.length >= request.topK) {
      break;
    }
  }

  return deduped;
}
