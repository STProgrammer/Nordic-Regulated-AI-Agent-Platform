import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ProtectedPage } from '@/components/auth/protected-page';
import { LanguageSwitcher } from '@/components/layout/language-switcher';
import { PlaceholderPage } from '@/components/layout/placeholder-page';
import { authApi } from '@/lib/api/auth';
import { ApiFailure, type CurrentUser } from '@/lib/api/contracts';
import { router } from '@/tests/test-navigation';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    updatePreferredLanguage: vi.fn(),
  },
}));

const mockedAuthApi = vi.mocked(authApi);
const currentUser: CurrentUser = {
  display_name: 'Syntetisk bruker',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Admin'],
  user_id: '22222222-2222-4222-8222-222222222222',
};

describe('authenticated shell', () => {
  it('renders landmarks, a skip link, active navigation, and honest placeholders', async () => {
    mockedAuthApi.getCurrentUser.mockResolvedValue(currentUser);
    renderWithProviders(<PlaceholderPage area="cases" />);

    expect(await screen.findByRole('heading', { name: 'Saksinnboks' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Hopp til hovedinnhold' })).toHaveAttribute(
      'href',
      '#main-content',
    );
    expect(screen.getByRole('navigation', { name: 'Hovednavigasjon' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Saker/ })).toHaveAttribute('aria-current', 'page');
    expect(
      screen.getByText('Saksinnboksen kommer i fase 9. Det finnes ingen saksdata å vise ennå.'),
    ).toBeInTheDocument();
  });

  it('shows an accessible progress indicator while an internal link navigation is pending', async () => {
    mockedAuthApi.getCurrentUser.mockResolvedValue(currentUser);
    const user = userEvent.setup();
    renderWithProviders(<PlaceholderPage area="cases" />);

    await screen.findByRole('heading', { name: 'Saksinnboks' });
    const approvalsLink = screen.getByRole('link', { name: 'Godkjenninger' });
    approvalsLink.addEventListener('click', (event) => event.preventDefault(), { once: true });
    await user.click(approvalsLink);

    expect(screen.getByRole('status')).toHaveTextContent('Åpner side …');
  });

  it('redirects an unauthenticated route to the localized login page with a safe return path', async () => {
    mockedAuthApi.getCurrentUser.mockRejectedValue(
      new ApiFailure({ code: 'authentication_required', status: 401 }),
    );
    renderWithProviders(
      <ProtectedPage>
        <p>Protected content</p>
      </ProtectedPage>,
    );

    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith('/nb/login?returnTo=%2Fnb%2Fcases'),
    );
  });

  it('shows a retryable state instead of treating an unavailable auth service as logout', async () => {
    mockedAuthApi.getCurrentUser.mockRejectedValue(
      new ApiFailure({ code: 'authentication_unavailable', status: 503 }),
    );
    renderWithProviders(
      <ProtectedPage>
        <p>Protected content</p>
      </ProtectedPage>,
    );

    expect(
      await screen.findByRole('heading', { name: 'Økten kan ikke kontrolleres nå' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Prøv på nytt' })).toBeInTheDocument();
  });

  it('preserves the localized route when switching language', async () => {
    const user = userEvent.setup();
    router.pathname = '/nb/audit';
    renderWithProviders(<LanguageSwitcher />);

    await user.click(screen.getByRole('button', { name: 'English' }));

    expect(router.replace).toHaveBeenCalledWith('/en/audit');
  });
});
