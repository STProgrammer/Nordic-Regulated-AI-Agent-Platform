import { afterEach, describe, expect, it, vi } from 'vitest';

import { auditApi } from '@/lib/api/audit';
import { ApiFailure } from '@/lib/api/contracts';

const eventId = '11111111-1111-4111-8111-111111111111';
const caseId = '22222222-2222-4222-8222-222222222222';

function response(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
}

afterEach(() => vi.unstubAllGlobals());

describe('Audit API client', () => {
  it('uses current-tenant filter parameters through a credentialed relative request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        data: {
          has_more: false,
          items: [
            {
              actor_user_id: null,
              case_id: caseId,
              event_id: eventId,
              event_type: 'workflow.completed',
              inserted_at: '2030-01-01T00:00:00Z',
              metadata: { status: 'completed' },
              resource_id: null,
              resource_type: 'workflow_run',
            },
          ],
          limit: 25,
          offset: 0,
          total: 1,
        },
        meta: {},
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      auditApi.list({ caseId, eventType: 'workflow.completed', limit: 25, offset: 0 }),
    ).resolves.toMatchObject({ total: 1 });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/audit/events?case_id=${caseId}&event_type=workflow.completed&limit=25&offset=0`,
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('rejects an unsafe metadata response before any trace or audit UI can render it', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        response({
          data: {
            has_more: false,
            items: [
              {
                actor_user_id: null,
                case_id: caseId,
                event_id: eventId,
                event_type: 'workflow.completed',
                inserted_at: '2030-01-01T00:00:00Z',
                metadata: { nested: { authorization: 'phase23-browser-secret' } },
                resource_id: null,
                resource_type: 'workflow_run',
              },
            ],
            limit: 25,
            offset: 0,
            total: 1,
          },
          meta: {},
        }),
      ),
    );

    await expect(auditApi.list()).rejects.toMatchObject({
      code: 'invalid_response',
      status: 200,
    } satisfies Partial<ApiFailure>);
  });
});
