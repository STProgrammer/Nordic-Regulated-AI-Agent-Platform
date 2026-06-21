import { afterEach, describe, expect, it, vi } from 'vitest';

import { approvalsApi } from '@/lib/api/approvals';
import { ApiFailure } from '@/lib/api/contracts';

const approvalId = '33333333-3333-4333-8333-333333333333';

function response(body: string | Blob, headers: Record<string, string>) {
  return new Response(body, { headers });
}

afterEach(() => vi.unstubAllGlobals());

describe('Approved-output API client', () => {
  it('downloads only a fixed server-owned attachment through the cookie-authenticated boundary', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response('{"safe":true}\n', {
        'Content-Disposition': 'attachment; filename="approved-output.json"',
        'Content-Type': 'application/json',
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(approvalsApi.exportApprovedOutput(approvalId, 'json')).resolves.toMatchObject({
      filename: 'approved-output.json',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/approvals/${approvalId}/exports/json`,
      expect.objectContaining({ credentials: 'include', method: 'POST' }),
    );
  });

  it('rejects unexpected attachment headers and sends only a closed mock target', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          response('not-a-pdf', {
            'Content-Disposition': 'attachment; filename="unsafe.pdf"',
            'Content-Type': 'application/pdf',
          }),
        )
        .mockResolvedValueOnce(
          response(
            JSON.stringify({
              data: {
                approval_id: approvalId,
                mode: 'mock',
                status: 'recorded',
                target: 'teams',
              },
              meta: {},
            }),
            { 'Content-Type': 'application/json' },
          ),
        ),
    );

    await expect(approvalsApi.exportApprovedOutput(approvalId, 'pdf')).rejects.toMatchObject({
      code: 'invalid_response',
      status: 200,
    } satisfies Partial<ApiFailure>);
    await expect(approvalsApi.recordMockHandoff(approvalId, { target: 'teams' })).resolves.toEqual({
      approval_id: approvalId,
      mode: 'mock',
      status: 'recorded',
      target: 'teams',
    });
  });
});
