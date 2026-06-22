import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

describe('Nordic civic UI primitives', () => {
  it('exposes explicit action variants and reserves alert semantics for errors', () => {
    render(
      <>
        <Button variant="secondary">Cancel</Button>
        <Alert>Informational notice</Alert>
        <Alert tone="error">Action failed</Alert>
      </>,
    );

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveClass('nordic-button-secondary');
    expect(screen.getByText('Informational notice')).not.toHaveAttribute('role', 'alert');
    expect(screen.getByRole('alert')).toHaveTextContent('Action failed');
  });
});
