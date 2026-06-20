import createMiddleware from 'next-intl/middleware';
import type { NextRequest } from 'next/server';

import { routing } from './i18n/routing';

const middleware = createMiddleware(routing);

export default function localeMiddleware(request: NextRequest) {
  return middleware(request);
}

export const config = {
  matcher: '/((?!api|_next|.*\\..*).*)',
};
