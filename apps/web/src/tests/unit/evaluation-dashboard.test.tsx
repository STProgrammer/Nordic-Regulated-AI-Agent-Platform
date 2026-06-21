import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { EvaluationDashboard } from '@/components/evaluation/evaluation-dashboard';
import { authApi } from '@/lib/api/auth';
import { evaluationsApi } from '@/lib/api/evaluations';
import type { CurrentUser, EvaluationRun } from '@/lib/api/contracts';
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

const admin: CurrentUser = {
  display_name: 'Synthetic administrator',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Admin'],
  user_id: '22222222-2222-4222-8222-222222222222',
};
const run: EvaluationRun = {
  dataset_content_hash: 'a'.repeat(64),
  dataset_key: 'nordic-regulated-core-v1',
  dataset_version: 'v1',
  evaluation_run_id: '33333333-3333-4333-8333-333333333333',
  finished_at: '2030-01-01T00:00:01Z',
  metrics: {
    average_latency_ms: null,
    case_total: 4,
    citation_mean: 1,
    cost_sample_count: 0,
    failed_case_total: 1,
    failure_code_counts: [{ code: 'citation_mismatch', count: 1 }],
    latency_sample_count: 0,
    passed_case_total: 3,
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
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(authApi.getCurrentUser).mockResolvedValue(admin);
  vi.mocked(evaluationsApi.listDatasets).mockResolvedValue({
    items: [
      {
        content_hash: 'a'.repeat(64),
        dataset_id: '44444444-4444-4444-8444-444444444444',
        dataset_key: 'nordic-regulated-core-v1',
        description: 'Synthetic deterministic evaluation corpus.',
        version: 'v1',
      },
    ],
  });
  vi.mocked(evaluationsApi.listRuns).mockResolvedValue({
    has_more: false,
    items: [run],
    limit: 25,
    offset: 0,
    total: 1,
  });
});

describe('Evaluation dashboard', () => {
  it('renders localized safe metrics and a run detail link for an Admin', async () => {
    renderWithProviders(<EvaluationDashboard />);

    expect(
      await screen.findByRole('heading', { name: 'KI-kvalitetsevaluering' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Strukturell trofasthet')).toBeInTheDocument();
    expect(screen.getAllByText('Ikke registrert')).not.toHaveLength(0);
    expect(screen.getAllByRole('link', { name: 'Åpne kjøring' })).toHaveLength(2);
    expect(screen.getAllByRole('link', { name: 'Åpne kjøring' })[0]).toHaveAttribute(
      'href',
      `/nb/evaluations/runs/${run.evaluation_run_id}`,
    );
    expect(screen.getByText(/deterministisk kontrollsignal/i)).toBeInTheDocument();
  });

  it('keeps data queries disabled for a non-Admin and uses the English translation', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({ ...admin, roles: ['Case Worker'] });
    renderWithProviders(<EvaluationDashboard />, 'en');

    expect(
      await screen.findByText("You do not have access to this organization's evaluations."),
    ).toBeInTheDocument();
    expect(evaluationsApi.listDatasets).not.toHaveBeenCalled();
    expect(evaluationsApi.listRuns).not.toHaveBeenCalled();
  });
});
