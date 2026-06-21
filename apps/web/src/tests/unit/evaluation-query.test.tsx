import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { evaluationsApi } from '@/lib/api/evaluations';
import {
  EVALUATION_POLL_INTERVAL_MS,
  evaluationPollInterval,
  evaluationQueryKeys,
  useEvaluationStart,
} from '@/lib/evaluations/query';

vi.mock('@/lib/api/evaluations', () => ({
  evaluationsApi: { start: vi.fn() },
}));

afterEach(() => vi.clearAllMocks());

describe('Evaluation queries', () => {
  it('polls only active run states at the bounded interval', () => {
    expect(evaluationPollInterval('queued')).toBe(EVALUATION_POLL_INTERVAL_MS);
    expect(evaluationPollInterval('running')).toBe(EVALUATION_POLL_INTERVAL_MS);
    expect(evaluationPollInterval('completed')).toBe(false);
    expect(evaluationPollInterval('failed')).toBe(false);
  });

  it('invalidates the evaluation boundary after a server-queued start', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    vi.mocked(evaluationsApi.start).mockResolvedValue({
      dataset_content_hash: 'a'.repeat(64),
      dataset_key: 'nordic-regulated-core-v1',
      dataset_version: 'v1',
      evaluation_run_id: '11111111-1111-4111-8111-111111111111',
      finished_at: null,
      metrics: {
        average_latency_ms: null,
        case_total: 0,
        citation_mean: null,
        cost_sample_count: 0,
        failed_case_total: 0,
        failure_code_counts: [],
        latency_sample_count: 0,
        passed_case_total: 0,
        refusal_mean: null,
        retrieval_mean: null,
        risk_mean: null,
        routing_mean: null,
        run_failure_code: null,
        structural_faithfulness_mean: null,
        total_cost_estimate: null,
      },
      pass_fail: 'pending',
      started_at: '2030-01-01T00:00:00Z',
      status: 'queued',
    });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useEvaluationStart(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync('nordic-regulated-core-v1');
    });

    expect(evaluationsApi.start).toHaveBeenCalledWith('nordic-regulated-core-v1');
    expect(invalidate).toHaveBeenCalledWith({ queryKey: evaluationQueryKeys.all });
  });
});
