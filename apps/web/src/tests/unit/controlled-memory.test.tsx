import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ControlledMemoryPanel } from '@/components/admin/controlled-memory-panel';
import { authApi } from '@/lib/api/auth';
import { memoryApi } from '@/lib/api/memory';
import type { CurrentUser } from '@/lib/api/contracts';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: { getCurrentUser: vi.fn(), updatePreferredLanguage: vi.fn() },
}));
vi.mock('@/lib/api/memory', () => ({
  memoryApi: {
    archiveEntry: vi.fn(),
    addEntry: vi.fn(),
    getSettings: vi.fn(),
    listEntries: vi.fn(),
    reviseEntry: vi.fn(),
    updateSettings: vi.fn(),
  },
}));

const currentUser: CurrentUser = {
  display_name: 'Syntetisk administrator',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Admin'],
  user_id: '22222222-2222-4222-8222-222222222222',
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(authApi.getCurrentUser).mockResolvedValue(currentUser);
  vi.mocked(memoryApi.getSettings).mockResolvedValue({ enabled: false });
  vi.mocked(memoryApi.listEntries).mockResolvedValue({ items: [] });
  vi.mocked(memoryApi.updateSettings).mockResolvedValue({ enabled: true });
  vi.mocked(memoryApi.addEntry).mockResolvedValue({
    archived_at: null,
    content: { locale: 'nb', preferred_term: 'avgjørelse', source_term: 'vedtak' },
    inserted_at: '2026-06-21T00:00:00Z',
    is_active: true,
    memory_entry_id: '33333333-3333-4333-8333-333333333333',
    memory_scope: 'organization',
    memory_type: 'approved_terminology',
    source: 'admin_approved',
    updated_at: '2026-06-21T00:00:00Z',
  });
});

describe('controlled-memory Admin panel', () => {
  it('shows only a safe empty Admin state and confirms enablement', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ControlledMemoryPanel />);

    expect(await screen.findByRole('heading', { name: 'Kontrollert minne' })).toBeInTheDocument();
    expect(screen.getByText('Ingen godkjente oppføringer ennå.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Aktiver kontrollert minne' }));

    await waitFor(() => expect(memoryApi.updateSettings).toHaveBeenCalledWith(true));
    expect(screen.queryByText(/namespace/i)).not.toBeInTheDocument();
  });

  it('shows a safe denied state to a non-Admin without calling memory APIs', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({ ...currentUser, roles: ['Case Worker'] });
    renderWithProviders(<ControlledMemoryPanel />);

    expect(
      await screen.findByText('Du har ikke tilgang til organisasjonens kontrollerte minne.'),
    ).toBeInTheDocument();
    expect(memoryApi.getSettings).not.toHaveBeenCalled();
  });
});
