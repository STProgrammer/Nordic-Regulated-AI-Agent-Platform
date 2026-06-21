import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { DraftingPanel } from '@/components/cases/drafting-panel';
import { authApi } from '@/lib/api/auth';
import { draftingApi } from '@/lib/api/drafting';
import { workflowsApi } from '@/lib/api/workflows';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: { getCurrentUser: vi.fn(), login: vi.fn(), logout: vi.fn() },
}));
vi.mock('@/lib/api/documents', () => ({ documentsApi: { getContext: vi.fn() } }));
vi.mock('@/lib/api/drafting', () => ({ draftingApi: { get: vi.fn() } }));
vi.mock('@/lib/api/workflows', () => ({
  workflowsApi: { get: vi.fn(), startDrafting: vi.fn() },
}));

const caseId = '44444444-4444-4444-8444-444444444444';
const documentId = '33333333-3333-4333-8333-333333333333';
const chunkId = '66666666-6666-4666-8666-666666666666';

describe('DraftingPanel', () => {
  it('starts only the closed language selector and presents the immutable review draft', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      display_name: 'Synthetic user',
      organization_id: '11111111-1111-4111-8111-111111111111',
      preferred_language: 'nb',
      roles: ['Case Worker'],
      user_id: '22222222-2222-4222-8222-222222222222',
    });
    vi.mocked(workflowsApi.startDrafting).mockResolvedValue({
      workflow_run_id: '77777777-7777-4777-8777-777777777777',
      workflow: 'drafting',
      status: 'completed',
      started_at: '2030-01-01T00:00:00Z',
      finished_at: '2030-01-01T00:00:00Z',
      intake: null,
      evidence: null,
      extraction: null,
      drafting: {
        evidence_available: true,
        draft_available: true,
        citation_count: 1,
        output_language: 'nb',
        draft_kind: 'response',
        reason_codes: [],
      },
    });
    vi.mocked(draftingApi.get).mockResolvedValue({
      workflow_run_id: '77777777-7777-4777-8777-777777777777',
      content: 'Syntetisk dokumenttekst for lokal nettlesertest [S1]',
      language: 'nb',
      draft_kind: 'response',
      citations: [{ citation_label: 'S1', document_id: documentId, chunk_id: chunkId }],
    });

    const actor = userEvent.setup();
    renderWithProviders(<DraftingPanel caseId={caseId} />);
    await actor.click(await screen.findByRole('button', { name: 'Start utkast' }));

    expect(
      await screen.findByText('Syntetisk dokumenttekst for lokal nettlesertest [S1]'),
    ).toBeInTheDocument();
    expect(workflowsApi.startDrafting).toHaveBeenCalledWith(caseId, 'nb');
    expect(screen.queryByRole('button', { name: /godkjenn|rediger/i })).not.toBeInTheDocument();
  });
});
