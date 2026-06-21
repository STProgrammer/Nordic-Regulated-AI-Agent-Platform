import { afterEach, describe, expect, it, vi } from 'vitest';

import { approvalsApi } from '@/lib/api/approvals';
import { ApiFailure } from '@/lib/api/contracts';

const approvalId = '33333333-3333-4333-8333-333333333333';
const caseId = '22222222-2222-4222-8222-222222222222';

function response(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
}

afterEach(() => vi.unstubAllGlobals());

describe('Approval API client', () => {
  it('sends only the closed approval payload through the cookie-authenticated API boundary', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        data: {
          approval_id: approvalId,
          approval_status: 'assigned',
          case_id: caseId,
          decision: 'approve',
          workflow_status: 'waiting_for_human_review',
        },
        meta: {},
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      approvalsApi.approve(approvalId, { reviewer_comment: 'Synthetic review' }),
    ).resolves.toMatchObject({
      decision: 'approve',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/approvals/${approvalId}/approve`,
      expect.objectContaining({
        body: JSON.stringify({ reviewer_comment: 'Synthetic review' }),
        credentials: 'include',
        method: 'POST',
      }),
    );
  });

  it('rejects malformed approval responses without exposing unsafe payloads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        response({
          data: {
            approval_id: approvalId,
            approval_status: 'pending',
            case_id: caseId,
            decision: null,
            workflow_status: 'waiting_for_human_review',
            raw_trace: 'must not be accepted',
          },
          meta: {},
        }),
      ),
    );

    await expect(approvalsApi.approve(approvalId, {})).rejects.toMatchObject({
      code: 'invalid_response',
      status: 200,
    } satisfies Partial<ApiFailure>);
  });
});
