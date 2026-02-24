import { buildCustomId, buildMetadata } from "./conventions";

export interface SupermemoryClientConfig {
  baseUrl: string;
  apiKey: string;
  timeoutMs?: number;
}

export interface IngestDocumentInput {
  tenantId: string;
  containerTag: string;
  namespace: string;
  source: string;
  externalId: string;
  content: string;
  userId?: string;
}

export interface SearchInput {
  query: string;
  containerTag: string;
  threshold: number;
  topK: number;
  userId?: string;
}

type HttpMethod = "GET" | "POST" | "PUT";

export class SupermemoryClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeoutMs: number;

  constructor(config: SupermemoryClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, "");
    this.apiKey = config.apiKey;
    this.timeoutMs = config.timeoutMs ?? 10_000;
  }

  private async request<T>(method: HttpMethod, endpoint: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method,
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`Supermemory request failed (${response.status})`);
      }
      return (await response.json()) as T;
    } finally {
      clearTimeout(timeout);
    }
  }

  async ingestDocument(input: IngestDocumentInput): Promise<Record<string, unknown>> {
    const customId = buildCustomId({
      tenantId: input.tenantId,
      namespace: input.namespace,
      externalId: input.externalId,
    });
    const metadata = buildMetadata({
      tenantId: input.tenantId,
      containerTag: input.containerTag,
      source: input.source,
      namespace: input.namespace,
      userId: input.userId,
    });
    return this.request<Record<string, unknown>>("POST", "/v3/documents", {
      customId,
      content: input.content,
      containerTag: input.containerTag,
      metadata,
    });
  }

  async search(input: SearchInput): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("POST", "/v4/search", {
      query: input.query,
      containerTag: input.containerTag,
      mode: "hybrid",
      threshold: input.threshold,
      limit: input.topK,
      userId: input.userId,
    });
  }

  async getUserProfile(containerTag: string, userId: string): Promise<Record<string, unknown>> {
    const encodedTag = encodeURIComponent(containerTag);
    const encodedUser = encodeURIComponent(userId);
    return this.request<Record<string, unknown>>(
      "GET",
      `/v1/user-profiles/${encodedTag}/${encodedUser}`,
    );
  }

  async upsertUserProfile(input: {
    containerTag: string;
    userId: string;
    traits: Record<string, unknown>;
  }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(
      "PUT",
      `/v1/user-profiles/${encodeURIComponent(input.containerTag)}/${encodeURIComponent(input.userId)}`,
      { traits: input.traits },
    );
  }
}
