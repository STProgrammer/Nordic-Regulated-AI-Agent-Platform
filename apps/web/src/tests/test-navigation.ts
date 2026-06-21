import { vi } from 'vitest';

export const router = {
  pathname: '/nb/cases',
  push: vi.fn<(path: string) => void>(),
  replace: vi.fn<(path: string) => void>(),
  search: '',
};

export function resetNavigation() {
  router.pathname = '/nb/cases';
  router.search = '';
  router.push.mockReset();
  router.replace.mockReset();
}
