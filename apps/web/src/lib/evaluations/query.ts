import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { evaluationsApi } from '@/lib/api/evaluations';
import { ApiFailure, type EvaluationStatus } from '@/lib/api/contracts';

const activeStatuses = new Set<EvaluationStatus>(['queued', 'running']);
export const EVALUATION_POLL_INTERVAL_MS = 1_500;

export function evaluationPollInterval(status: EvaluationStatus | undefined): number | false {
  return status && activeStatuses.has(status) ? EVALUATION_POLL_INTERVAL_MS : false;
}

export const evaluationQueryKeys = {
  all: ['evaluations'] as const,
  datasets: () => [...evaluationQueryKeys.all, 'datasets'] as const,
  runs: (limit: number, offset: number, status?: EvaluationStatus) =>
    [...evaluationQueryKeys.all, 'runs', { limit, offset, status: status ?? null }] as const,
  run: (runId: string) => [...evaluationQueryKeys.all, 'run', runId] as const,
  result: (runId: string, resultId: string) =>
    [...evaluationQueryKeys.all, 'run', runId, 'result', resultId] as const,
};

function shouldRetryEvaluationQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiFailure && [400, 401, 403, 404, 409, 422].includes(error.status)) {
    return false;
  }
  return failureCount < 1;
}

export function useEvaluationDatasets(enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => evaluationsApi.listDatasets(),
    queryKey: evaluationQueryKeys.datasets(),
    retry: shouldRetryEvaluationQuery,
  });
}

export function useEvaluationRuns({
  enabled = true,
  limit = 25,
  offset = 0,
  status,
}: {
  enabled?: boolean;
  limit?: number;
  offset?: number;
  status?: EvaluationStatus;
} = {}) {
  return useQuery({
    enabled,
    queryFn: () => evaluationsApi.listRuns(status ? { limit, offset, status } : { limit, offset }),
    queryKey: evaluationQueryKeys.runs(limit, offset, status),
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => evaluationPollInterval(item.status) !== false)
        ? EVALUATION_POLL_INTERVAL_MS
        : false,
    retry: shouldRetryEvaluationQuery,
  });
}

export function useEvaluationRun(runId: string, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => evaluationsApi.getRun(runId),
    queryKey: evaluationQueryKeys.run(runId),
    refetchInterval: (query) =>
      query.state.data ? evaluationPollInterval(query.state.data.run.status) : false,
    retry: shouldRetryEvaluationQuery,
  });
}

export function useEvaluationResult(runId: string, resultId: string, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => evaluationsApi.getResult(runId, resultId),
    queryKey: evaluationQueryKeys.result(runId, resultId),
    retry: shouldRetryEvaluationQuery,
  });
}

export function useEvaluationStart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (datasetKey: string) => evaluationsApi.start(datasetKey),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: evaluationQueryKeys.all });
    },
  });
}
