import {
  caseDomainSchema,
  casePrioritySchema,
  caseRiskLevelSchema,
  caseStatusSchema,
  type CaseDomain,
  type CasePriority,
  type CaseRiskLevel,
  type CaseStatus,
} from '@/lib/api/contracts';

export const CASE_PAGE_SIZE = 25;
export const caseSortValues = [
  'inserted_at',
  'updated_at',
  'case_number',
  'title',
  'due_date',
  'priority',
  'status',
] as const;

export type CaseSort = (typeof caseSortValues)[number];
export type CaseDirection = 'asc' | 'desc';

export type CaseFilters = {
  status?: CaseStatus | undefined;
  riskLevel?: CaseRiskLevel | undefined;
  assignedUserId?: string | undefined;
  domain?: CaseDomain | undefined;
  priority?: CasePriority | undefined;
  query?: string | undefined;
  limit: number;
  offset: number;
  sort: CaseSort;
  direction: CaseDirection;
};

export type CaseFilterInput = {
  [Key in keyof CaseFilters]?: CaseFilters[Key] | undefined;
};

function enumValue<T>(
  schema: { safeParse(value: unknown): { success: boolean; data?: T } },
  value: string | null,
): T | undefined {
  if (!value) return undefined;
  const result = schema.safeParse(value);
  return result.success ? result.data : undefined;
}

function safeUuid(value: string | null): string | undefined {
  return value &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
    ? value
    : undefined;
}

function boundedInteger(
  value: string | null,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  if (!value || !/^\d+$/.test(value)) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= minimum && parsed <= maximum ? parsed : fallback;
}

export function normalizeCaseFilters(filters: CaseFilterInput): CaseFilters {
  const query = filters.query?.trim();
  return {
    assignedUserId: safeUuid(filters.assignedUserId ?? null),
    direction: filters.direction === 'asc' ? 'asc' : 'desc',
    domain: enumValue(caseDomainSchema, filters.domain ?? null),
    limit: Math.min(100, Math.max(1, filters.limit ?? CASE_PAGE_SIZE)),
    offset: Math.max(0, filters.offset ?? 0),
    priority: enumValue(casePrioritySchema, filters.priority ?? null),
    query: query && query.length <= 200 ? query : undefined,
    riskLevel: enumValue(caseRiskLevelSchema, filters.riskLevel ?? null),
    sort: caseSortValues.includes(filters.sort as CaseSort)
      ? (filters.sort as CaseSort)
      : 'inserted_at',
    status: enumValue(caseStatusSchema, filters.status ?? null),
  };
}

export function caseFiltersFromSearchParams(searchParams: URLSearchParams): CaseFilters {
  return normalizeCaseFilters({
    assignedUserId: searchParams.get('assignee') ?? undefined,
    direction: searchParams.get('direction') === 'asc' ? 'asc' : 'desc',
    domain: (searchParams.get('domain') ?? undefined) as CaseDomain | undefined,
    limit: boundedInteger(searchParams.get('limit'), CASE_PAGE_SIZE, 1, 100),
    offset: boundedInteger(searchParams.get('offset'), 0, 0, Number.MAX_SAFE_INTEGER),
    priority: (searchParams.get('priority') ?? undefined) as CasePriority | undefined,
    query: searchParams.get('q') ?? undefined,
    riskLevel: (searchParams.get('risk') ?? undefined) as CaseRiskLevel | undefined,
    sort: searchParams.get('sort') as CaseSort | undefined,
    status: (searchParams.get('status') ?? undefined) as CaseStatus | undefined,
  });
}

export function caseFiltersToSearchParams(filters: CaseFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.query) params.set('q', filters.query);
  if (filters.status) params.set('status', filters.status);
  if (filters.riskLevel) params.set('risk', filters.riskLevel);
  if (filters.assignedUserId) params.set('assignee', filters.assignedUserId);
  if (filters.domain) params.set('domain', filters.domain);
  if (filters.priority) params.set('priority', filters.priority);
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.limit !== CASE_PAGE_SIZE) params.set('limit', String(filters.limit));
  if (filters.sort !== 'inserted_at') params.set('sort', filters.sort);
  if (filters.direction !== 'desc') params.set('direction', filters.direction);
  return params;
}

export function hasCaseFilters(filters: CaseFilters): boolean {
  return Boolean(
    filters.assignedUserId ||
    filters.domain ||
    filters.priority ||
    filters.query ||
    filters.riskLevel ||
    filters.status,
  );
}
