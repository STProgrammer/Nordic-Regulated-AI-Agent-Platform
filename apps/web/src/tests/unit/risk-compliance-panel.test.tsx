import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { RiskCompliancePanel } from '@/components/cases/risk-compliance-panel';
import { authApi } from '@/lib/api/auth';
import { riskApi } from '@/lib/api/risk';
import { workflowsApi } from '@/lib/api/workflows';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({ authApi: { getCurrentUser: vi.fn() } }));
vi.mock('@/lib/api/risk', () => ({ riskApi: { get: vi.fn() } }));
vi.mock('@/lib/api/workflows', () => ({
  workflowsApi: { get: vi.fn(), startRiskCompliance: vi.fn() },
}));

const caseId = '11111111-1111-4111-8111-111111111111';
const runId = '77777777-7777-4777-8777-777777777777';

describe('RiskCompliancePanel', () => {
  it('shows a closed high-risk assessment and no reviewer action', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      display_name: 'Synthetic user',
      organization_id: '33333333-3333-4333-8333-333333333333',
      preferred_language: 'nb',
      roles: ['Case Worker'],
      user_id: '22222222-2222-4222-8222-222222222222',
    });
    vi.mocked(workflowsApi.startRiskCompliance).mockResolvedValue({
      finished_at: '2030-01-01T00:00:00Z',
      risk_compliance: {
        final_risk_level: 'high',
        requires_approval: true,
        risk_reasons: ['pii_detected', 'policy_conflict'],
        safe_next_state: 'human_review_required',
      },
      started_at: '2030-01-01T00:00:00Z',
      status: 'completed',
      workflow: 'risk_compliance',
      workflow_run_id: runId,
    });
    vi.mocked(riskApi.get).mockResolvedValue({
      requires_approval: true,
      risk_level: 'high',
      risk_reasons: ['pii_detected', 'policy_conflict'],
      safe_next_state: 'human_review_required',
      workflow_run_id: runId,
    });

    const actor = userEvent.setup();
    renderWithProviders(<RiskCompliancePanel caseId={caseId} />);
    await actor.click(await screen.findByRole('button', { name: 'Start risikovurdering' }));

    expect(await screen.findByText('Høy risiko')).toBeInTheDocument();
    expect(
      screen.getByText('Menneskelig kontroll vil være påkrevd i en senere arbeidsflyt.'),
    ).toBeInTheDocument();
    expect(workflowsApi.startRiskCompliance).toHaveBeenCalledWith(caseId);
    expect(
      screen.queryByRole('button', { name: /godkjenn|avvis|rediger/i }),
    ).not.toBeInTheDocument();
  });
});
