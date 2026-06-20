import { useQuery } from '@tanstack/react-query';

import { documentsApi } from '@/lib/api/documents';
import { ApiFailure, type DocumentData, type DocumentList } from '@/lib/api/contracts';

export const documentQueryKeys = {
  all: ['documents'] as const,
  detail: (documentId: string) => [...documentQueryKeys.all, 'detail', documentId] as const,
  lists: () => [...documentQueryKeys.all, 'list'] as const,
  list: (caseId: string, limit: number, offset: number) =>
    [...documentQueryKeys.lists(), { caseId, limit, offset }] as const,
};

export function shouldRetryDocumentQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiFailure && [400, 401, 403, 404, 409, 422].includes(error.status)) {
    return false;
  }
  return failureCount < 1;
}

export function useDocumentList(caseId: string, limit = 25, offset = 0) {
  return useQuery<DocumentList, ApiFailure>({
    enabled: Boolean(caseId),
    queryFn: () => documentsApi.list({ caseId, limit, offset }),
    queryKey: documentQueryKeys.list(caseId, limit, offset),
    retry: shouldRetryDocumentQuery,
  });
}

export function useDocumentDetail(documentId: string | null) {
  return useQuery<DocumentData, ApiFailure>({
    enabled: documentId !== null,
    queryFn: () => documentsApi.get(documentId ?? ''),
    queryKey: documentQueryKeys.detail(documentId ?? ''),
    retry: shouldRetryDocumentQuery,
  });
}
