import {
  apiRequest,
  caseAssigneeListSchema,
  caseSubmissionInputSchema,
  caseDetailSchema,
  caseListSchema,
  jsonRequest,
  type CaseAssigneeList,
  type CaseSubmissionInput,
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
  submit(input: CaseSubmissionInput): Promise<CaseDetail> {
    const payload = caseSubmissionInputSchema.parse(input);
    return apiRequest(casePath(), caseDetailSchema, jsonRequest('POST', payload));
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
