import { afterEach, describe, expect, it, vi } from 'vitest';

import { casesApi } from '@/lib/api/cases';
import { ApiFailure } from '@/lib/api/contracts';

const caseId = '33333333-3333-4333-8333-333333333333';
const summary = {
  assigned_user_id: null,
  case_id: caseId,
  case_number: 'CASE-SYNTHETIC',
  domain: 'public_sector',
  due_date: '2030-02-03',
  inserted_at: '2030-01-01T10:00:00Z',
  language: 'nb',
  priority: 'normal',
  risk_level: null,
  status: 'new',
  submitted_by_user_id: '22222222-2222-4222-8222-222222222222',
  title: 'Synthetic case',
  updated_at: '2030-01-01T10:00:00Z',
};

function response(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
}
afterEach(() => vi.unstubAllGlobals());

describe('Case API client', () => {
  it('serializes normalized filters into a credentialed relative request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        data: { items: [summary], limit: 25, offset: 0, total: 1, has_more: false },
        meta: {},
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await expect(casesApi.list({ query: '  Synthetic  ', status: 'new' })).resolves.toMatchObject({
      total: 1,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/cases?q=Synthetic&status=new',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('rejects malformed case payloads without exposing a response body', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(response({ data: { ...summary, case_id: 'not-a-uuid' }, meta: {} })),
    );
    await expect(casesApi.get(caseId)).rejects.toMatchObject({
      code: 'invalid_response',
      status: 200,
    } satisfies Partial<ApiFailure>);
  });
});
