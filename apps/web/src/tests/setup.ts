import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

import { resetNavigation, router } from './test-navigation';

vi.mock('next/link', async () => {
  const React = await import('react');

  return {
    default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) =>
      React.createElement('a', { href, ...props }, children),
  };
});

vi.mock('next/navigation', () => ({
  usePathname: () => router.pathname,
  useRouter: () => ({ replace: router.replace }),
  useSearchParams: () => new URLSearchParams(router.search),
}));

afterEach(() => {
  cleanup();
  resetNavigation();
  vi.restoreAllMocks();
});
