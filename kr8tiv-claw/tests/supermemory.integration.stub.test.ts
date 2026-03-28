import { describe, expect, it, vi } from 'vitest';
import { SupermemoryClient, SupermemoryConventions } from '../src/supermemory/client.js';

describe('supermemory wrapper integration stubs (mock HTTP)', () => {
  it('sends tenant-scoped ingestion payload with customId dedupe conventions', async () => {
    const mockFetch = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } })
    );

    const client = new SupermemoryClient({ apiKey: 'scoped-key', containerTag: 'tenant-tag', fetchImpl: mockFetch as typeof fetch });
    await client.ingestDocument({ customId: 'doc:1', content: 'hello', metadata: { kind: 'note' } });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.containerTag).toBe('tenant-tag');
    expect(body.customId).toBe('doc:1');
    expect(body.metadata.dedupeBy).toBe('customId');
    expect(body.metadata.source).toBe('kr8tiv-claw');
  });

  it('uses hybrid retrieval with threshold clamp + user profile fields', async () => {
    const mockFetch = vi.fn(async () =>
      new Response(JSON.stringify({ hits: [] }), { status: 200, headers: { 'content-type': 'application/json' } })
    );

    const client = new SupermemoryClient({ apiKey: 'scoped-key', containerTag: 'tenant-tag', fetchImpl: mockFetch as typeof fetch });
    await client.retrieve({ query: 'where is policy', threshold: 2, userId: 'u-1' });

    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.strategy).toBe('hybrid');
    expect(body.mode).toBe('hybrid');
    expect(body.query).toBe('where is policy');
    expect(body.q).toBe('where is policy');
    expect(body.threshold).toBe(1);
    expect(body.userId).toBe('u-1');
  });

  it('upserts user profiles with convention-based customId', async () => {
    const mockFetch = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } })
    );

    const client = new SupermemoryClient({ apiKey: 'scoped-key', containerTag: 'tenant-tag', fetchImpl: mockFetch as typeof fetch });
    await client.upsertUserProfile('user-7', { name: 'Ada' });

    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.customId).toBe(SupermemoryConventions.profileCustomId('user-7'));
    expect(body.metadata.kind).toBe('user-profile');
  });

  it('retries transient 5xx failures', async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce(new Response('oops', { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }));

    const client = new SupermemoryClient({
      apiKey: 'scoped-key',
      containerTag: 'tenant-tag',
      fetchImpl: mockFetch as typeof fetch,
      maxRetries: 1
    });

    const result = await client.retrieve({ query: 'retry me' });
    expect(result).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('normalizes search response variants into deduped context lines', async () => {
    const mockFetch = vi.fn(async () =>
      new Response(
        JSON.stringify({
          hits: [
            { content: 'alpha' },
            { text: 'alpha' },
            { snippet: 'beta' },
            { content: 'gamma' }
          ]
        }),
        { status: 200, headers: { 'content-type': 'application/json' } }
      )
    );

    const client = new SupermemoryClient({ apiKey: 'scoped-key', containerTag: 'tenant-tag', fetchImpl: mockFetch as typeof fetch });
    const lines = await client.retrieveContextLines({ query: 'test', limit: 2 });

    expect(lines).toEqual(['alpha', 'beta']);
  });
});
