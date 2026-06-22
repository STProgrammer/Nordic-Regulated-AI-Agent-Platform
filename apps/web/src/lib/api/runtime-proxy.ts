const FORWARDED_REQUEST_HEADERS = [
  'accept',
  'accept-language',
  'content-type',
  'cookie',
  'origin',
  'x-request-id',
] as const;

const FORWARDED_RESPONSE_HEADERS = [
  'cache-control',
  'content-type',
  'retry-after',
  'www-authenticate',
  'x-request-id',
] as const;

type FetchImplementation = typeof fetch;

export function runtimeApiOrigin(value = process.env.API_ORIGIN): URL | undefined {
  if (!value) {
    return undefined;
  }

  try {
    const url = new URL(value);
    if (
      !['http:', 'https:'].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      url.pathname !== '/'
    ) {
      return undefined;
    }
    return url;
  } catch {
    return undefined;
  }
}

export async function proxyApiRequest(
  request: Request,
  path: readonly string[],
  fetchImplementation: FetchImplementation = fetch,
): Promise<Response> {
  const origin = runtimeApiOrigin();
  if (!origin) {
    return unavailableResponse();
  }

  const upstreamUrl = new URL(
    `/api/${path.map((segment) => encodeURIComponent(segment)).join('/')}`,
    origin,
  );
  upstreamUrl.search = new URL(request.url).search;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  const init: RequestInit & { duplex?: 'half' } = {
    headers,
    method: request.method,
  };
  if (hasBody && request.body !== null) {
    init.body = request.body;
    init.duplex = 'half';
  }

  try {
    const upstream = await fetchImplementation(upstreamUrl, init);
    return proxyResponse(upstream);
  } catch {
    return unavailableResponse();
  }
}

function proxyResponse(upstream: Response): Response {
  const headers = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }

  const getSetCookie = (upstream.headers as Headers & { getSetCookie?: () => string[] })
    .getSetCookie;
  const cookies = getSetCookie?.call(upstream.headers) ?? responseCookies(upstream.headers);
  for (const cookie of cookies) {
    headers.append('set-cookie', cookie);
  }

  return new Response(upstream.body, { headers, status: upstream.status });
}

function responseCookies(headers: Headers): string[] {
  const cookie = headers.get('set-cookie');
  return cookie === null ? [] : [cookie];
}

function unavailableResponse(): Response {
  return Response.json(
    {
      error: {
        code: 'api_unavailable',
        details: null,
        message: 'The API service is temporarily unavailable.',
        request_id: null,
      },
    },
    {
      headers: { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' },
      status: 503,
    },
  );
}
