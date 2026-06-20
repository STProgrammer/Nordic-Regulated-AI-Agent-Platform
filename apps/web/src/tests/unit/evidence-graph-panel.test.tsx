import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { EvidenceGraphPanel } from '@/components/evidence/evidence-graph-panel';
import { authApi } from '@/lib/api/auth';
import { documentsApi } from '@/lib/api/documents';
import { workflowsApi } from '@/lib/api/workflows';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: { getCurrentUser: vi.fn(), login: vi.fn(), logout: vi.fn() },
}));
vi.mock('@/lib/api/documents', () => ({
  documentsApi: { getContext: vi.fn() },
}));
vi.mock('@/lib/api/workflows', () => ({
  workflowsApi: { get: vi.fn(), startEvidence: vi.fn() },
}));

const caseId = '44444444-4444-4444-8444-444444444444';
const documentId = '33333333-3333-4333-8333-333333333333';
const chunkId = '55555555-5555-4555-8555-555555555555';
const runId = '66666666-6666-4666-8666-666666666666';
const startedAt = '2030-01-01T00:00:00Z';

describe('EvidenceGraphPanel', () => {
  it('starts only the closed Evidence operation and opens source context on demand', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      display_name: 'Synthetic user',
      organization_id: '11111111-1111-4111-8111-111111111111',
      preferred_language: 'nb',
      roles: ['Case Worker'],
      user_id: '22222222-2222-4222-8222-222222222222',
    });
    vi.mocked(workflowsApi.startEvidence).mockResolvedValue({
      workflow_run_id: runId,
      workflow: 'evidence',
      status: 'completed',
      started_at: startedAt,
      finished_at: startedAt,
      intake: null,
      evidence: {
        outcome: 'completed',
        sufficient: true,
        contradiction_detected: false,
        reason_codes: [],
        citation_labels: ['S1'],
        sources: [
          {
            citation_label: 'S1',
            document_id: documentId,
            chunk_id: chunkId,
            source_status: 'approved',
            warning_codes: [],
          },
        ],
      },
    });
    vi.mocked(documentsApi.getContext).mockResolvedValue({
      document_id: documentId,
      chunk_id: chunkId,
      document_title: 'Synthetic document',
      document_file_type: 'txt',
      source_status: 'approved',
      page_number: 1,
      section_title: null,
      context: 'Synthetic bounded source context.',
      truncated: false,
    });

    const actor = userEvent.setup();
    renderWithProviders(<EvidenceGraphPanel caseId={caseId} />);
    await actor.click(await screen.findByRole('button', { name: 'Bygg kildepakke' }));
    expect(await screen.findByText('S1')).toBeInTheDocument();
    await actor.click(screen.getByRole('button', { name: 'Åpne kildekontekst' }));
    expect(await screen.findByText('Synthetic bounded source context.')).toBeInTheDocument();
    await waitFor(() => expect(documentsApi.getContext).toHaveBeenCalledWith(documentId, chunkId));
  });
});
