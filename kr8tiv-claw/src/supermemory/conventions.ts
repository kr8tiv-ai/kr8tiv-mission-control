export interface SupermemoryMetadata {
  tenantId: string;
  containerTag: string;
  source: string;
  userId?: string;
  namespace: string;
}

export function buildContainerTag(prefix: string, tenantId: string): string {
  return `${prefix}:${tenantId}`;
}

export function buildCustomId(input: {
  tenantId: string;
  namespace: string;
  externalId: string;
}): string {
  const ext = input.externalId.trim().toLowerCase().replace(/[^a-z0-9-:_]/g, "-");
  return `${input.tenantId}:${input.namespace}:${ext}`;
}

export function buildMetadata(input: {
  tenantId: string;
  containerTag: string;
  source: string;
  namespace: string;
  userId?: string;
}): SupermemoryMetadata {
  return {
    tenantId: input.tenantId,
    containerTag: input.containerTag,
    source: input.source,
    namespace: input.namespace,
    userId: input.userId,
  };
}
