import { afterEach, describe, expect, it, vi } from 'vitest';

import { proxyApiRequest, runtimeApiOrigin } from '@/lib/api/runtime-proxy';

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('runtime API proxy', () => {
  it('reads the upstream origin at request time and rejects unsafe values', () => {
    vi.stubEnv('API_ORIGIN', 'http://api:8000');
    expect(runtimeApiOrigin()?.toString()).toBe('http://api:8000/');

    vi.stubEnv('API_ORIGIN', 'https://user:password@api.example.invalid');
    expect(runtimeApiOrigin()).toBeUndefined();
  });

  it('forwards the allowlisted request headers, query, body, and safe response metadata', async () => {
    vi.stubEnv('API_ORIGIN', 'http://api:8000');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { logged_out: true } }), {
        headers: {
          'Cache-Control': 'no-store',
          'Content-Type': 'application/json',
          'Retry-After': '30',
          'Set-Cookie': 'nordic_session=opaque; HttpOnly; Path=/',
          'X-Request-ID': 'request-42',
        },
        status: 429,
      }),
    );
    const request = new Request('http://web.test/api/auth/logout?source=web', {
      body: JSON.stringify({ reason: 'user_requested' }),
      headers: {
        Authorization: 'Bearer never-forwarded',
        'Content-Type': 'application/json',
        Cookie: 'nordic_session=opaque',
        Host: 'attacker.invalid',
        Origin: 'https://app.example.invalid',
        'X-Request-ID': 'request-42',
      },
      method: 'POST',
    });

    const response = await proxyApiRequest(request, ['auth', 'logout'], fetchMock);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.objectContaining({ href: 'http://api:8000/api/auth/logout?source=web' }),
      expect.objectContaining({ body: request.body, method: 'POST' }),
    );
    const forwardedHeaders = new Headers(fetchMock.mock.calls[0]?.[1].headers);
    expect(forwardedHeaders.get('authorization')).toBeNull();
    expect(forwardedHeaders.get('cookie')).toBe('nordic_session=opaque');
    expect(forwardedHeaders.get('origin')).toBe('https://app.example.invalid');
    expect(response.status).toBe(429);
    expect(response.headers.get('retry-after')).toBe('30');
    expect(response.headers.get('set-cookie')).toContain('nordic_session=opaque');
    expect(response.headers.get('x-request-id')).toBe('request-42');
  });

  it('returns a safe 503 without calling an upstream when configuration is missing or unavailable', async () => {
    vi.stubEnv('API_ORIGIN', '');
    const fetchMock = vi.fn();
    const response = await proxyApiRequest(
      new Request('http://web.test/api/auth/me'),
      ['auth', 'me'],
      fetchMock,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: 'api_unavailable', request_id: null },
    });
  });
});
