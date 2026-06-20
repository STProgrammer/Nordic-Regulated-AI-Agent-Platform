import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ExtractionPanel } from '@/components/cases/extraction-panel';
import { authApi } from '@/lib/api/auth';
import { extractionApi } from '@/lib/api/extraction';
import { workflowsApi } from '@/lib/api/workflows';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: { getCurrentUser: vi.fn(), login: vi.fn(), logout: vi.fn() },
}));
vi.mock('@/lib/api/documents', () => ({ documentsApi: { getContext: vi.fn() } }));
vi.mock('@/lib/api/extraction', () => ({ extractionApi: { list: vi.fn(), edit: vi.fn() } }));
vi.mock('@/lib/api/workflows', () => ({
  workflowsApi: { get: vi.fn(), startExtraction: vi.fn() },
}));

const caseId = '44444444-4444-4444-8444-444444444444';
const fieldId = '55555555-5555-4555-8555-555555555555';
const documentId = '33333333-3333-4333-8333-333333333333';
const chunkId = '66666666-6666-4666-8666-666666666666';

describe('ExtractionPanel', () => {
  it('starts only Extraction and sends a typed field value for a bounded human edit', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      display_name: 'Synthetic user',
      organization_id: '11111111-1111-4111-8111-111111111111',
      preferred_language: 'nb',
      roles: ['Case Worker'],
      user_id: '22222222-2222-4222-8222-222222222222',
    });
    vi.mocked(workflowsApi.startExtraction).mockResolvedValue({
      workflow_run_id: '77777777-7777-4777-8777-777777777777',
      workflow: 'extraction',
      status: 'completed',
      started_at: '2030-01-01T00:00:00Z',
      finished_at: '2030-01-01T00:00:00Z',
      intake: null,
      evidence: null,
      extraction: {
        evidence_available: true,
        extraction_schema: 'conservative_v1',
        extracted_field_count: 1,
        low_confidence_field_count: 1,
      },
    });
    vi.mocked(extractionApi.list).mockResolvedValue([
      {
        field_id: fieldId,
        workflow_run_id: '77777777-7777-4777-8777-777777777777',
        field_kind: 'reference_numbers',
        field_value: { references: ['SYN-1'] },
        confidence_band: 'low',
        source_document_id: documentId,
        source_chunk_id: chunkId,
        human_edited: false,
        updated_at: '2030-01-01T00:00:00Z',
      },
    ]);
    vi.mocked(extractionApi.edit).mockResolvedValue({
      field_id: fieldId,
      workflow_run_id: '77777777-7777-4777-8777-777777777777',
      field_kind: 'reference_numbers',
      field_value: { references: ['SYN-2'] },
      confidence_band: 'low',
      source_document_id: documentId,
      source_chunk_id: chunkId,
      human_edited: true,
      updated_at: '2030-01-01T00:00:00Z',
    });
    const actor = userEvent.setup();
    renderWithProviders(<ExtractionPanel caseId={caseId} />);
    await actor.click(await screen.findByRole('button', { name: 'Start ekstraksjon' }));
    expect(await screen.findByText('SYN-1')).toBeInTheDocument();
    await actor.click(screen.getByRole('button', { name: 'Rediger opplysning' }));
    const editor = screen.getByLabelText('Verdi (én opplysning per linje)');
    await actor.clear(editor);
    await actor.type(editor, 'SYN-2');
    await actor.click(screen.getByRole('button', { name: 'Lagre endring' }));
    await waitFor(() =>
      expect(extractionApi.edit).toHaveBeenCalledWith(caseId, fieldId, {
        field_value: { references: ['SYN-2'] },
      }),
    );
  });
});
