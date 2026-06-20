import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { LoginForm } from '@/components/auth/login-form';
import { authApi } from '@/lib/api/auth';
import { ApiFailure, type CurrentUser } from '@/lib/api/contracts';
import { router } from '@/tests/test-navigation';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

const mockedAuthApi = vi.mocked(authApi);
const currentUser: CurrentUser = {
  display_name: 'Syntetisk bruker',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Case Worker'],
  user_id: '22222222-2222-4222-8222-222222222222',
};

describe('LoginForm', () => {
  it('uses Bokmål labels, validates required input, clears the password, and redirects after session refresh', async () => {
    const user = userEvent.setup();
    mockedAuthApi.login.mockResolvedValue(currentUser);
    mockedAuthApi.getCurrentUser.mockResolvedValue(currentUser);
    renderWithProviders(<LoginForm />);

    await user.click(screen.getByRole('button', { name: 'Logg inn' }));
    expect(await screen.findByText('Skriv inn en gyldig e-postadresse.')).toBeInTheDocument();

    await user.type(screen.getByLabelText('E-postadresse'), 'worker@demo.invalid');
    const password = screen.getByLabelText('Passord');
    await user.type(password, 'synthetic-password');
    await user.click(screen.getByRole('button', { name: 'Logg inn' }));

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/nb/cases'));
    expect(mockedAuthApi.login).toHaveBeenCalledWith({
      email: 'worker@demo.invalid',
      password: 'synthetic-password',
    });
    expect(password).toHaveValue('');
  });

  it('renders English labels and safe localized rate-limit feedback', async () => {
    const user = userEvent.setup();
    mockedAuthApi.login.mockRejectedValue(
      new ApiFailure({ code: 'login_rate_limited', retryAfterSeconds: 18, status: 429 }),
    );
    renderWithProviders(<LoginForm />, 'en');

    await user.type(screen.getByLabelText('Email address'), 'worker@demo.invalid');
    await user.type(screen.getByLabelText('Password'), 'synthetic-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(
      await screen.findByText('Too many sign-in attempts. Try again in 18 seconds.'),
    ).toBeInTheDocument();
  });
});
