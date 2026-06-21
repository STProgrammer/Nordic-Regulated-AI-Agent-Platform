import { apiRequest, auditEventListSchema, type AuditEventList } from '@/lib/api/contracts';

export type AuditFilterInput = {
  caseId?: string;
  eventType?: string;
  insertedAfter?: string;
  insertedBefore?: string;
  limit?: number;
  offset?: number;
  resourceType?: string;
};

function filterQuery(filters: AuditFilterInput): URLSearchParams {
  const query = new URLSearchParams();
  const values: [string, string | number | undefined][] = [
    ['case_id', filters.caseId],
    ['event_type', filters.eventType?.trim()],
    ['resource_type', filters.resourceType?.trim()],
    ['inserted_after', filters.insertedAfter],
    ['inserted_before', filters.insertedBefore],
    ['limit', filters.limit],
    ['offset', filters.offset],
  ];
  for (const [key, value] of values) {
    if (value !== undefined && value !== '') query.set(key, String(value));
  }
  return query;
}

export const auditApi = {
  list(filters: AuditFilterInput = {}): Promise<AuditEventList> {
    const query = filterQuery(filters);
    return apiRequest(
      `/api/audit/events${query.size ? `?${query.toString()}` : ''}`,
      auditEventListSchema,
    );
  },

  listCase(caseId: string, limit = 25, offset = 0): Promise<AuditEventList> {
    const query = filterQuery({ limit, offset });
    return apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/audit${query.size ? `?${query.toString()}` : ''}`,
      auditEventListSchema,
    );
  },
};
