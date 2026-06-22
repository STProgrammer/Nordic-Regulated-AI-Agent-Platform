import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { CaseInbox } from '@/components/cases/case-inbox';
import { authApi } from '@/lib/api/auth';
import { casesApi } from '@/lib/api/cases';
import type { CurrentUser } from '@/lib/api/contracts';
import { router } from '@/tests/test-navigation';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: { getCurrentUser: vi.fn(), login: vi.fn(), logout: vi.fn() },
}));
vi.mock('@/lib/api/cases', () => ({
  casesApi: { create: vi.fn(), get: vi.fn(), list: vi.fn(), listAssignees: vi.fn() },
}));
const mockedAuthApi = vi.mocked(authApi);
const mockedCasesApi = vi.mocked(casesApi);
const user = {
  display_name: 'Syntetisk bruker',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Case Worker'] as CurrentUser['roles'],
  user_id: '22222222-2222-4222-8222-222222222222',
};
const item = {
  assigned_user_id: null,
  case_id: '33333333-3333-4333-8333-333333333333',
  case_number: 'CASE-SYNTHETIC',
  domain: 'public_sector' as const,
  due_date: '2030-02-03',
  inserted_at: '2030-01-01T10:00:00Z',
  language: 'nb' as const,
  priority: 'normal' as const,
  risk_level: null,
  status: 'new' as const,
  submitted_by_user_id: user.user_id,
  title: 'Syntetisk sak',
  updated_at: '2030-01-01T10:00:00Z',
};

describe('CaseInbox', () => {
  it('renders localized real case data and puts search filters in the route', async () => {
    mockedAuthApi.getCurrentUser.mockResolvedValue(user);
    mockedCasesApi.list.mockResolvedValue({
      items: [item],
      limit: 25,
      offset: 0,
      total: 1,
      has_more: false,
    });
    mockedCasesApi.listAssignees.mockResolvedValue({ items: [] });
    const actor = userEvent.setup();
    renderWithProviders(<CaseInbox />);
    expect(await screen.findByRole('heading', { name: 'Saksinnboks' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'CASE-SYNTHETIC' })).toHaveAttribute(
      'href',
      `/nb/cases/${item.case_id}`,
    );
    expect(screen.getByText('Ikke vurdert')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Saker i saksinnboksen' })).toHaveAttribute(
      'aria-describedby',
      'case-table-scroll-hint',
    );
    expect(screen.getByText('Skroll vannrett for å se alle kolonnene.')).toBeInTheDocument();
    expect(screen.getByTestId('case-table-viewport')).toHaveClass('nordic-table-viewport');
    expect(screen.getByTestId('case-table-scrollbar-top')).toHaveClass(
      'nordic-table-scrollbar-top',
    );
    expect(screen.getByTestId('case-table-scrollbar-top')).toHaveAttribute('role', 'region');
    expect(screen.getByTestId('case-table-scrollbar-top')).toHaveAttribute(
      'aria-label',
      'Skroll vannrett for å se alle kolonnene.',
    );
    await actor.type(screen.getByLabelText('Søk i saker'), 'syntetisk');
    await actor.click(screen.getByRole('button', { name: 'Bruk filtre' }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/nb/cases?q=syntetisk'));
  });
});
