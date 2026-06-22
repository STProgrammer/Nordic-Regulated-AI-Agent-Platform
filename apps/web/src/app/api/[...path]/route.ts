import { proxyApiRequest } from '@/lib/api/runtime-proxy';
import type { NextRequest } from 'next/server';

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return proxyApiRequest(request, path);
}

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export const DELETE = proxy;
export const GET = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
export const PATCH = proxy;
export const POST = proxy;
export const PUT = proxy;
