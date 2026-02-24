import { afterEach, describe, expect, test, vi } from "vitest";

import { SupermemoryClient } from "../src/supermemory/client";
import { retrieveHybridContext } from "../src/supermemory/retrieval";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("supermemory client", () => {
  test("ingest uses customId dedupe convention and metadata", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const client = new SupermemoryClient({
      baseUrl: "https://api.supermemory.ai",
      apiKey: "test-key",
    });
    await client.ingestDocument({
      tenantId: "tenant-a",
      containerTag: "tenant:tenant-a",
      namespace: "arena",
      source: "task-mode",
      externalId: "Task/ABC-123",
      content: "result text",
      userId: "user-1",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    const payload = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(payload.customId).toBe("tenant-a:arena:task-abc-123");
    expect(payload.containerTag).toBe("tenant:tenant-a");
    expect(payload.metadata).toMatchObject({
      tenantId: "tenant-a",
      source: "task-mode",
      namespace: "arena",
      userId: "user-1",
    });
  });

  test("retrieveHybridContext dedupes and respects topK", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => {
      return new Response(
        JSON.stringify({
          results: [
            { content: "alpha" },
            { text: "beta" },
            { snippet: "alpha" },
            { content: "gamma" },
          ],
        }),
        { status: 200 },
      );
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const client = new SupermemoryClient({
      baseUrl: "https://api.supermemory.ai",
      apiKey: "test-key",
    });
    const result = await retrieveHybridContext(client, {
      query: "task",
      containerTag: "tenant:demo",
      threshold: 0.5,
      topK: 2,
    });

    expect(result).toEqual(["alpha", "beta"]);
  });

  test("user profile helpers use scoped URL paths", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => {
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const client = new SupermemoryClient({
      baseUrl: "https://api.supermemory.ai",
      apiKey: "test-key",
    });
    await client.getUserProfile("tenant:acme", "user/123");
    await client.upsertUserProfile({
      containerTag: "tenant:acme",
      userId: "user/123",
      traits: { tier: "vip" },
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.supermemory.ai/v1/user-profiles/tenant%3Aacme/user%2F123",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.supermemory.ai/v1/user-profiles/tenant%3Aacme/user%2F123",
      expect.objectContaining({ method: "PUT" }),
    );
  });
});
