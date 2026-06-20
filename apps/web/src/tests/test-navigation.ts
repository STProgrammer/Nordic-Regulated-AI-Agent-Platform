import { vi } from 'vitest';

export const router = {
  pathname: '/nb/cases',
  replace: vi.fn<(path: string) => void>(),
  search: '',
};

export function resetNavigation() {
  router.pathname = '/nb/cases';
  router.search = '';
  router.replace.mockReset();
}
