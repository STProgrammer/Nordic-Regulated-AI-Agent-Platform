import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PriorityBadge, RiskBadge, StatusBadge } from '@/components/cases/case-badge';
import { renderWithProviders } from '@/tests/test-utils';

describe('case state indicators', () => {
  it('communicates state with a localized label as well as semantic visual treatment', () => {
    renderWithProviders(
      <>
        <StatusBadge value="approved" />
        <PriorityBadge value="urgent" />
        <RiskBadge value="critical" />
      </>,
    );

    expect(screen.getByText('Godkjent')).toHaveClass('nordic-status-success');
    expect(screen.getByText('Haster')).toHaveClass('nordic-status-danger');
    expect(screen.getByText('Kritisk')).toHaveClass('nordic-status-danger');
  });
});
