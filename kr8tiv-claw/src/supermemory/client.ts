export type SupermemoryClientOptions = {
  baseUrl?: string;
  apiKey: string;
  containerTag: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  maxRetries?: number;
};

export type IngestDocumentInput = {
  customId: string;
  content: string;
  metadata?: Record<string, unknown>;
};

export type RetrieveInput = {
  query: string;
  threshold?: number;
  limit?: number;
  metadata?: Record<string, unknown>;
  userId?: string;
};

export type SupermemorySearchResponse = {
  results?: Array<Record<string, unknown>>;
  hits?: Array<Record<string, unknown>>;
  items?: Array<Record<string, unknown>>;
  data?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

export const SupermemoryConventions = {
  source: 'kr8tiv-claw',
  dedupeBy: 'customId',
  profileCustomId: (userId: string): string => `profile:${userId}`
};

/**
 * Tenant-scoped Supermemory API wrapper.
 * - Uses per-tenant scoped API key
 * - Requires per-tenant containerTag
 * - Applies conventions for customId dedupe and metadata tagging
 */
export class SupermemoryClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly containerTag: string;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;

  constructor(opts: SupermemoryClientOptions) {
    this.baseUrl = opts.baseUrl ?? 'https://api.supermemory.ai';
    this.apiKey = opts.apiKey;
    this.containerTag = opts.containerTag;
    this.fetchImpl = opts.fetchImpl ?? fetch;
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this.maxRetries = opts.maxRetries ?? 1;
  }

  async ingestDocument(input: IngestDocumentInput): Promise<unknown> {
    return this.request('/v3/documents', {
      method: 'POST',
      body: JSON.stringify({
        content: input.content,
        customId: input.customId,
        containerTag: this.containerTag,
        metadata: {
          ...input.metadata,
          source: SupermemoryConventions.source,
          dedupeBy: SupermemoryConventions.dedupeBy
        }
      })
    });
  }

  async retrieve(input: RetrieveInput): Promise<SupermemorySearchResponse> {
    return (await this.request('/v4/search', {
      method: 'POST',
      body: JSON.stringify({
        query: input.query,
        q: input.query,
        containerTag: this.containerTag,
        mode: 'hybrid',
        strategy: 'hybrid',
        threshold: normalizeThreshold(input.threshold),
        limit: input.limit ?? 8,
        metadata: input.metadata,
        userId: input.userId
      })
    })) as SupermemorySearchResponse;
  }

  /**
   * Retrieve search results and normalize response variants into plain text lines.
   */
  async retrieveContextLines(input: RetrieveInput): Promise<string[]> {
    const payload = await this.retrieve(input);
    const limit = Math.max(1, input.limit ?? 8);
    const deduped: string[] = [];
    const seen = new Set<string>();

    for (const line of extractTextCandidates(payload)) {
      if (seen.has(line)) {
        continue;
      }
      seen.add(line);
      deduped.push(line.slice(0, 240));
      if (deduped.length >= limit) {
        break;
      }
    }

    return deduped;
  }

  async upsertUserProfile(userId: string, profile: Record<string, unknown>): Promise<unknown> {
    return this.request('/v3/documents', {
      method: 'POST',
      body: JSON.stringify({
        content: JSON.stringify(profile),
        customId: SupermemoryConventions.profileCustomId(userId),
        containerTag: this.containerTag,
        metadata: {
          kind: 'user-profile',
          userId,
          source: SupermemoryConventions.source,
          dedupeBy: SupermemoryConventions.dedupeBy
        }
      })
    });
  }

  private async request(path: string, init: RequestInit): Promise<unknown> {
    let attempt = 0;
    let lastError: Error | undefined;

    while (attempt <= this.maxRetries) {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

        const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
          ...init,
          signal: controller.signal,
          headers: {
            authorization: `Bearer ${this.apiKey}`,
            'content-type': 'application/json',
            ...(init.headers ?? {})
          }
        });

        clearTimeout(timeout);

        if (!response.ok) {
          const body = await response.text();
          const isRetriable = response.status >= 500 && response.status < 600;
          if (isRetriable && attempt < this.maxRetries) {
            attempt += 1;
            continue;
          }
          throw new Error(`Supermemory API error ${response.status}: ${body}`);
        }

        return response.json();
      } catch (error) {
        lastError = error as Error;
        if (attempt >= this.maxRetries) break;
        attempt += 1;
      }
    }

    throw lastError ?? new Error('Supermemory request failed without error details');
  }
}

function normalizeThreshold(threshold: number | undefined): number {
  const value = threshold ?? 0.35;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function extractTextCandidates(payload: SupermemorySearchResponse): string[] {
  const source = payload.results ?? payload.hits ?? payload.items ?? payload.data ?? [];
  if (!Array.isArray(source)) {
    return [];
  }

  const lines: string[] = [];
  for (const item of source) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const maybeText = (item as Record<string, unknown>).content
      ?? (item as Record<string, unknown>).text
      ?? (item as Record<string, unknown>).snippet;
    if (typeof maybeText === 'string' && maybeText.trim().length > 0) {
      lines.push(maybeText.trim().replace(/\s+/g, ' '));
    }
  }

  return lines;
}
