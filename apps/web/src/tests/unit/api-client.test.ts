import { afterEach, describe, expect, it, vi } from 'vitest';

import { authApi } from '@/lib/api/auth';
import { ApiFailure } from '@/lib/api/contracts';

const currentUser = {
  display_name: 'Syntetisk bruker',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Case Worker'],
  user_id: '22222222-2222-4222-8222-222222222222',
};

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json', ...headers },
    status,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Phase 6 auth API client', () => {
  it('sends a credentialed relative login request and parses the success envelope', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ data: currentUser, meta: { request_id: 'request-1' } }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      authApi.login({ email: 'worker@demo.invalid', password: 'synthetic-password' }),
    ).resolves.toEqual(currentUser);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        body: JSON.stringify({ email: 'worker@demo.invalid', password: 'synthetic-password' }),
        credentials: 'include',
        method: 'POST',
      }),
    );
  });

  it('parses current-user and logout envelopes through the same credentialed boundary', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ data: currentUser, meta: { request_id: 'request-me' } }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ data: { logged_out: true }, meta: { request_id: 'request-logout' } }),
      );
    vi.stubGlobal('fetch', fetchMock);

    await expect(authApi.getCurrentUser()).resolves.toEqual(currentUser);
    await expect(authApi.logout()).resolves.toEqual({ logged_out: true });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/auth/logout',
      expect.objectContaining({ credentials: 'include', method: 'POST' }),
    );
  });

  it('preserves safe request and rate-limit metadata on a typed API failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: 'login_rate_limited',
              details: null,
              message: 'Too many login attempts.',
              request_id: 'request-42',
            },
          },
          429,
          { 'Retry-After': '42', 'X-Request-ID': 'header-request-42' },
        ),
      ),
    );

    await expect(
      authApi.login({ email: 'worker@demo.invalid', password: 'synthetic-password' }),
    ).rejects.toMatchObject({
      code: 'login_rate_limited',
      requestId: 'header-request-42',
      retryAfterSeconds: 42,
      status: 429,
    } satisfies Partial<ApiFailure>);
  });

  it('rejects a malformed successful response without exposing its body', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ data: { display_name: 'Only this field' } })),
    );

    await expect(authApi.getCurrentUser()).rejects.toMatchObject({
      code: 'invalid_response',
      status: 200,
    } satisfies Partial<ApiFailure>);
  });
});
