import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { EvaluationResultDetail } from '@/components/evaluation/evaluation-result-detail';
import { authApi } from '@/lib/api/auth';
import { evaluationsApi } from '@/lib/api/evaluations';
import type { CurrentUser, EvaluationResult } from '@/lib/api/contracts';
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
const result: EvaluationResult = {
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
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(authApi.getCurrentUser).mockResolvedValue(user);
  vi.mocked(evaluationsApi.getResult).mockResolvedValue(result);
});

describe('Evaluation result detail', () => {
  it('shows only the safe result fields and preserves absent telemetry', async () => {
    renderWithProviders(
      <EvaluationResultDetail evaluationResultId={resultId} evaluationRunId={runId} />,
    );

    expect(
      await screen.findByRole('heading', { name: 'Detaljer for evalueringsresultat' }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('synthetic_case')).not.toHaveLength(0);
    expect(screen.getAllByText('Ikke registrert')).not.toHaveLength(0);
    expect(screen.getByText('citation_mismatch')).toBeInTheDocument();
    expect(screen.queryByText(/prompt|source|query/i)).not.toBeInTheDocument();
  });
});
