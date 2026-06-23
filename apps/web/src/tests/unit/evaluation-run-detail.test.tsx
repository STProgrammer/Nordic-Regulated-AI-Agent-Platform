import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { EvaluationRunDetail } from '@/components/evaluation/evaluation-run-detail';
import { authApi } from '@/lib/api/auth';
import { evaluationsApi } from '@/lib/api/evaluations';
import type {
  CurrentUser,
  EvaluationRunDetail as EvaluationRunDetailData,
} from '@/lib/api/contracts';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({ authApi: { getCurrentUser: vi.fn() } }));
vi.mock('@/lib/api/evaluations', () => ({
  evaluationsApi: {
    exportReport: vi.fn(),
    getResult: vi.fn(),
    getRun: vi.fn(),
    listDatasets: vi.fn(),
    listRuns: vi.fn(),
    start: vi.fn(),
  },
}));

const runId = '33333333-3333-4333-8333-333333333333';
const resultId = '44444444-4444-4444-8444-444444444444';
const user: CurrentUser = {
  display_name: 'Synthetic administrator',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Admin'],
  user_id: '22222222-2222-4222-8222-222222222222',
};
const detail: EvaluationRunDetailData = {
  results: [
    {
      case_key: 'synthetic_case',
      citation_score: 0,
      cost_estimate: null,
      evaluation_result_id: resultId,
      failure_codes: ['citation_mismatch'],
      latency_ms: null,
      passed: false,
      refusal_score: 1,
      retrieval_score: 1,
      risk_score: 1,
      routing_score: 1,
      structural_faithfulness_score: 1,
    },
  ],
  run: {
    dataset_content_hash: 'a'.repeat(64),
    dataset_key: 'nordic-regulated-core-v1',
    dataset_version: 'v1',
    evaluation_run_id: runId,
    finished_at: '2030-01-01T00:00:01Z',
    metrics: {
      average_latency_ms: null,
      case_total: 1,
      citation_mean: 0,
      cost_sample_count: 0,
      failed_case_total: 1,
      failure_code_counts: [{ code: 'citation_mismatch', count: 1 }],
      latency_sample_count: 0,
      passed_case_total: 0,
      refusal_mean: 1,
      retrieval_mean: 1,
      risk_mean: 1,
      routing_mean: 1,
      run_failure_code: null,
      structural_faithfulness_mean: 1,
      total_cost_estimate: null,
    },
    pass_fail: 'fail',
    started_at: '2030-01-01T00:00:00Z',
    status: 'completed',
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(authApi.getCurrentUser).mockResolvedValue(user);
  vi.mocked(evaluationsApi.getRun).mockResolvedValue(detail);
});

describe('Evaluation run detail', () => {
  it('links a failed case to its safe result record and offers only terminal report export', async () => {
    renderWithProviders(<EvaluationRunDetail evaluationRunId={runId} />);

    expect(
      await screen.findByRole('heading', { name: 'Detaljer for evalueringskjøring' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'synthetic_case' })).toHaveAttribute(
      'href',
      `/nb/evaluations/runs/${runId}/results/${resultId}`,
    );
    expect(screen.getByTestId('evaluation-report-download')).toBeInTheDocument();
    expect(screen.getByTestId('evaluation-run-status')).toHaveTextContent('Fullført');
    expect(screen.getByText('citation_mismatch')).toBeInTheDocument();
  });
});
