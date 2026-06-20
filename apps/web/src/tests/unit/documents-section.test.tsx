import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { DocumentsSection } from '@/components/documents/documents-section';
import { authApi } from '@/lib/api/auth';
import { documentsApi } from '@/lib/api/documents';
import type { CurrentUser, DocumentData } from '@/lib/api/contracts';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: { getCurrentUser: vi.fn(), login: vi.fn(), logout: vi.fn() },
}));
vi.mock('@/lib/api/documents', () => ({
  documentsApi: {
    get: vi.fn(),
    getContext: vi.fn(),
    list: vi.fn(),
    reindex: vi.fn(),
    updateSourceStatus: vi.fn(),
  },
}));

const mockedAuthApi = vi.mocked(authApi);
const mockedDocumentsApi = vi.mocked(documentsApi);
const caseId = '44444444-4444-4444-8444-444444444444';
const document: DocumentData = {
  case_id: caseId,
  confidentiality_level: 'internal',
  document_id: '33333333-3333-4333-8333-333333333333',
  file_size_bytes: 12,
  file_type: 'txt',
  indexed_at: '2030-01-01T10:00:00Z',
  indexing_error: null,
  indexing_status: 'indexed',
  inserted_at: '2030-01-01T10:00:00Z',
  language: 'nb',
  mime_type: 'text/plain',
  original_filename: 'synthetic.txt',
  page_count: 1,
  parsing_error: null,
  parsing_status: 'parsed',
  source_status: 'approved',
  title: 'Syntetisk dokument',
  updated_at: '2030-01-01T10:00:00Z',
  uploaded_by_user_id: '22222222-2222-4222-8222-222222222222',
};
const administrator = {
  display_name: 'Syntetisk administrator',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Admin'] as CurrentUser['roles'],
  user_id: document.uploaded_by_user_id,
};

describe('DocumentsSection', () => {
  it('renders safe lifecycle metadata and exposes governed controls only as affordances', async () => {
    mockedAuthApi.getCurrentUser.mockResolvedValue(administrator);
    mockedDocumentsApi.list.mockResolvedValue({
      has_more: false,
      items: [document],
      limit: 25,
      offset: 0,
      total: 1,
    });
    mockedDocumentsApi.get.mockResolvedValue(document);
    mockedDocumentsApi.updateSourceStatus.mockResolvedValue({
      ...document,
      source_status: 'deprecated',
    });
    mockedDocumentsApi.reindex.mockResolvedValue({ ...document, indexing_status: 'pending' });
    const actor = userEvent.setup();
    renderWithProviders(<DocumentsSection caseId={caseId} />);

    expect(await screen.findByText('Syntetisk dokument')).toBeInTheDocument();
    await actor.click(screen.getByRole('button', { name: 'Se metadata' }));
    expect(await screen.findByRole('heading', { name: 'Dokumentmetadata' })).toBeInTheDocument();
    expect(screen.getByText('Tolking')).toBeInTheDocument();
    expect(screen.getByText('Indeksering')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Be om reindeksering' })).toBeInTheDocument();

    await actor.selectOptions(screen.getByLabelText('Endre kildestatus'), 'deprecated');
    await actor.click(screen.getByRole('button', { name: 'Lagre kildestatus' }));
    await waitFor(() =>
      expect(mockedDocumentsApi.updateSourceStatus).toHaveBeenCalledWith(
        document.document_id,
        'deprecated',
      ),
    );
  });
});
