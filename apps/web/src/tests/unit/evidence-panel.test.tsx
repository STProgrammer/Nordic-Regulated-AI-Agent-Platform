import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { EvidencePanel, sourceLabel } from '@/components/evidence/evidence-panel';
import { authApi } from '@/lib/api/auth';
import { documentsApi } from '@/lib/api/documents';
import { retrievalApi } from '@/lib/api/retrieval';
import type { CurrentUser, RetrievalSource } from '@/lib/api/contracts';
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
vi.mock('@/lib/api/retrieval', () => ({ retrievalApi: { search: vi.fn() } }));

const mockedAuthApi = vi.mocked(authApi);
const mockedDocumentsApi = vi.mocked(documentsApi);
const mockedRetrievalApi = vi.mocked(retrievalApi);
const caseId = '44444444-4444-4444-8444-444444444444';
const documentId = '33333333-3333-4333-8333-333333333333';
const chunkId = '55555555-5555-4555-8555-555555555555';
const user = {
  display_name: 'Syntetisk bruker',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Case Worker'] as CurrentUser['roles'],
  user_id: '22222222-2222-4222-8222-222222222222',
};
const source: RetrievalSource = {
  chunk_id: chunkId,
  document_file_type: 'txt',
  document_id: documentId,
  document_title: 'Syntetisk dokument',
  excerpt: 'Syntetisk utdrag fra en tillatt kilde.',
  page_number: 1,
  rank: 1,
  rank_score: 0.42,
  retrieval_methods: ['semantic', 'keyword'],
  section_title: null,
  source_status: 'approved',
  warning_codes: [],
};

describe('EvidencePanel', () => {
  it('searches approved sources and opens context only after an explicit action', async () => {
    mockedAuthApi.getCurrentUser.mockResolvedValue(user);
    mockedDocumentsApi.list.mockResolvedValue({
      has_more: false,
      items: [],
      limit: 25,
      offset: 0,
      total: 0,
    });
    mockedRetrievalApi.search.mockResolvedValue([source]);
    mockedDocumentsApi.getContext.mockResolvedValue({
      chunk_id: chunkId,
      context: 'Syntetisk avgrenset kontekst.',
      document_file_type: 'txt',
      document_id: documentId,
      document_title: source.document_title,
      page_number: 1,
      section_title: null,
      source_status: 'approved',
      truncated: true,
    });
    const actor = userEvent.setup();
    renderWithProviders(<EvidencePanel caseId={caseId} />);

    await actor.type(await screen.findByLabelText('Hva vil du finne i kildene?'), 'kontroll');
    await actor.click(screen.getByRole('button', { name: 'Søk i kilder' }));
    expect(await screen.findByText('Syntetisk utdrag fra en tillatt kilde.')).toBeInTheDocument();
    expect(mockedRetrievalApi.search).toHaveBeenCalledWith({
      case_id: caseId,
      limit: 10,
      query: 'kontroll',
    });
    expect(screen.getByText(/Rang 1 · rangeringssignal/)).toBeInTheDocument();

    await actor.click(screen.getByRole('button', { name: 'Åpne kildekontekst' }));
    expect(
      await screen.findByRole('dialog', { name: 'Avgrenset kildekontekst' }),
    ).toBeInTheDocument();
    expect(await screen.findByText('Syntetisk avgrenset kontekst.')).toBeInTheDocument();
    expect(screen.getByText('Denne konteksten er avkortet av tjenesten.')).toBeInTheDocument();
    await waitFor(() =>
      expect(mockedDocumentsApi.getContext).toHaveBeenCalledWith(documentId, chunkId),
    );
  });

  it('builds a display-only source label with location fallbacks', () => {
    expect(sourceLabel(source, 'Side 1', 'Del kontroll')).toBe('Syntetisk dokument · TXT · Side 1');
    expect(
      sourceLabel(
        { ...source, page_number: null, section_title: 'Kontroll' },
        'Side',
        'Del Kontroll',
      ),
    ).toBe('Syntetisk dokument · TXT · Del Kontroll');
  });
});
