import { afterEach, describe, expect, it, vi } from 'vitest';

import { documentsApi } from '@/lib/api/documents';

const documentId = '33333333-3333-4333-8333-333333333333';
const caseId = '44444444-4444-4444-8444-444444444444';
const chunkId = '55555555-5555-4555-8555-555555555555';
const documentData = {
  case_id: caseId,
  confidentiality_level: 'internal',
  document_id: documentId,
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
  title: 'Synthetic document',
  updated_at: '2030-01-01T10:00:00Z',
  uploaded_by_user_id: '22222222-2222-4222-8222-222222222222',
};

function response(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
}

afterEach(() => vi.unstubAllGlobals());

describe('Document API client', () => {
  it('uses credentialed relative endpoints and accepts only safe document shapes', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response({
          data: { has_more: false, items: [documentData], limit: 25, offset: 0, total: 1 },
          meta: {},
        }),
      )
      .mockResolvedValueOnce(
        response({ data: { ...documentData, source_status: 'deprecated' }, meta: {} }),
      )
      .mockResolvedValueOnce(
        response({
          data: {
            chunk_id: chunkId,
            context: 'Synthetic bounded context',
            document_file_type: 'txt',
            document_id: documentId,
            document_title: 'Synthetic document',
            page_number: 1,
            section_title: null,
            source_status: 'deprecated',
            truncated: true,
          },
          meta: {},
        }),
      );
    vi.stubGlobal('fetch', fetchMock);

    await expect(documentsApi.list({ caseId })).resolves.toMatchObject({ total: 1 });
    await expect(documentsApi.updateSourceStatus(documentId, 'deprecated')).resolves.toMatchObject({
      source_status: 'deprecated',
    });
    await expect(documentsApi.getContext(documentId, chunkId)).resolves.toMatchObject({
      context: 'Synthetic bounded context',
      truncated: true,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `/api/documents?case_id=${caseId}&limit=25&offset=0`,
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `/api/documents/${documentId}/source-status`,
      expect.objectContaining({ credentials: 'include', method: 'PATCH' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      `/api/documents/${documentId}/context?chunk_id=${chunkId}`,
      expect.objectContaining({ credentials: 'include' }),
    );
  });
});
