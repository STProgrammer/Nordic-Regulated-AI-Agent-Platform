import { useQuery } from '@tanstack/react-query';

import { auditApi, type AuditFilterInput } from '@/lib/api/audit';
import { ApiFailure, type AuditEventList, type WorkflowTrace } from '@/lib/api/contracts';
import { workflowsApi } from '@/lib/api/workflows';

export const auditQueryKeys = {
  all: ['audit'] as const,
  events: (filters: AuditFilterInput) => [...auditQueryKeys.all, 'events', filters] as const,
  trace: (runId: string) => [...auditQueryKeys.all, 'trace', runId] as const,
};

export function shouldRetryAuditQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiFailure && [400, 401, 403, 404, 422].includes(error.status)) return false;
  return failureCount < 1;
}

export function useAuditEvents(filters: AuditFilterInput) {
  return useQuery<AuditEventList, ApiFailure>({
    queryFn: () => auditApi.list(filters),
    queryKey: auditQueryKeys.events(filters),
    retry: shouldRetryAuditQuery,
  });
}

export function useWorkflowTrace(runId: string, enabled = true) {
  return useQuery<WorkflowTrace, ApiFailure>({
    enabled,
    queryFn: () => workflowsApi.getTrace(runId),
    queryKey: auditQueryKeys.trace(runId),
    retry: shouldRetryAuditQuery,
  });
}
