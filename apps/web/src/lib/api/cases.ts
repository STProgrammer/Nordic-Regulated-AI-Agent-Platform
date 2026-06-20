import {
  apiRequest,
  caseAssigneeListSchema,
  caseCreateInputSchema,
  caseDetailSchema,
  caseListSchema,
  type CaseAssigneeList,
  type CaseCreateInput,
  type CaseDetail,
  type CaseList,
} from '@/lib/api/contracts';
import {
  caseFiltersToSearchParams,
  normalizeCaseFilters,
  type CaseFilterInput,
} from '@/lib/cases/filters';

function casePath(path = ''): string {
  return `/api/cases${path}`;
}

export const casesApi = {
  create(input: CaseCreateInput): Promise<CaseDetail> {
    const payload = caseCreateInputSchema.parse(input);
    return apiRequest(casePath(), caseDetailSchema, {
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },

  get(caseId: string): Promise<CaseDetail> {
    return apiRequest(casePath(`/${encodeURIComponent(caseId)}`), caseDetailSchema);
  },

  list(filters: CaseFilterInput = {}): Promise<CaseList> {
    const normalized = normalizeCaseFilters(filters);
    const query = caseFiltersToSearchParams(normalized);
    return apiRequest(
      query.size ? `${casePath()}?${query.toString()}` : casePath(),
      caseListSchema,
    );
  },

  listAssignees(): Promise<CaseAssigneeList> {
    return apiRequest(casePath('/assignees'), caseAssigneeListSchema);
  },
};
