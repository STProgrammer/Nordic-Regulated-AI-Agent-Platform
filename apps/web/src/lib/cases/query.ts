import { useQuery } from '@tanstack/react-query';

import { casesApi } from '@/lib/api/cases';
import { ApiFailure, type CaseDetail, type CaseList } from '@/lib/api/contracts';
import { normalizeCaseFilters, type CaseFilterInput, type CaseFilters } from '@/lib/cases/filters';

export const caseQueryKeys = {
  all: ['cases'] as const,
  assignees: () => [...caseQueryKeys.all, 'assignees'] as const,
  detail: (caseId: string) => [...caseQueryKeys.all, 'detail', caseId] as const,
  lists: () => [...caseQueryKeys.all, 'list'] as const,
  list: (filters: CaseFilters) => [...caseQueryKeys.lists(), filters] as const,
};

export function shouldRetryCaseQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiFailure && [400, 401, 403, 404, 422].includes(error.status)) return false;
  return failureCount < 1;
}

export function useCaseList(filters: CaseFilterInput) {
  const normalized = normalizeCaseFilters(filters);
  return useQuery<CaseList, ApiFailure>({
    queryFn: () => casesApi.list(normalized),
    queryKey: caseQueryKeys.list(normalized),
    retry: shouldRetryCaseQuery,
  });
}

export function useCaseDetail(caseId: string, enabled = true) {
  return useQuery<CaseDetail, ApiFailure>({
    enabled,
    queryFn: () => casesApi.get(caseId),
    queryKey: caseQueryKeys.detail(caseId),
    retry: shouldRetryCaseQuery,
  });
}

export function useCaseAssignees() {
  return useQuery({
    queryFn: casesApi.listAssignees,
    queryKey: caseQueryKeys.assignees(),
    retry: shouldRetryCaseQuery,
  });
}
