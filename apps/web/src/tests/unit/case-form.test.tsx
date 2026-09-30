import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { CaseForm } from '@/components/cases/case-form';
import { casesApi } from '@/lib/api/cases';
import { router } from '@/tests/test-navigation';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/cases', () => ({
  casesApi: { submit: vi.fn(), get: vi.fn(), list: vi.fn(), listAssignees: vi.fn() },
}));
const mockedCasesApi = vi.mocked(casesApi);
const submittedCase = {
  assigned_user_id: null,
  archived_at: null,
  case_id: '33333333-3333-4333-8333-333333333333',
  case_number: 'CASE-SYNTHETIC',
  case_type: null,
  description: 'Syntetisk beskrivelse',
  domain: 'public_sector' as const,
  due_date: null,
  external_reference: null,
  inserted_at: '2030-01-01T10:00:00Z',
  language: 'nb' as const,
  priority: 'normal' as const,
  risk_level: null,
  status: 'new' as const,
  submitted_by_user_id: '22222222-2222-4222-8222-222222222222',
  title: 'Syntetisk sak',
  updated_at: '2030-01-01T10:00:00Z',
};

describe('CaseForm', () => {
  it('validates required fields and submits only supported case input', async () => {
    mockedCasesApi.submit.mockResolvedValue(submittedCase);
    const actor = userEvent.setup();
    renderWithProviders(<CaseForm />);
    await actor.click(screen.getByRole('button', { name: 'Opprett sak' }));
    expect(await screen.findAllByText('Fyll ut dette feltet.')).not.toHaveLength(0);
    await actor.type(screen.getByLabelText('Tittel'), 'Syntetisk sak');
    await actor.type(screen.getByLabelText('Beskrivelse'), 'Syntetisk beskrivelse');
    await actor.click(screen.getByRole('button', { name: 'Opprett sak' }));
    await waitFor(() =>
      expect(mockedCasesApi.submit).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Syntetisk sak',
          description: 'Syntetisk beskrivelse',
          domain: 'public_sector',
          priority: 'normal',
          language: 'nb',
        }),
      ),
    );
    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith(`/nb/cases/${submittedCase.case_id}`),
    );
  });
});
