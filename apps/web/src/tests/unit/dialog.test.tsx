import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { Dialog } from '@/components/ui/dialog';

function DialogHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} type="button">
        Open confirmation
      </button>
      {open ? (
        <Dialog
          description="This action is recorded."
          kind="alertdialog"
          onClose={() => setOpen(false)}
          title="Confirm action"
        >
          <div className="mt-4 flex gap-3">
            <button type="button">Confirm</button>
            <button onClick={() => setOpen(false)} type="button">
              Cancel
            </button>
          </div>
        </Dialog>
      ) : null}
    </>
  );
}

describe('Dialog', () => {
  it('labels the modal, contains keyboard focus, and restores focus after Escape', async () => {
    const user = userEvent.setup();
    render(<DialogHarness />);

    const opener = screen.getByRole('button', { name: 'Open confirmation' });
    await user.click(opener);

    expect(screen.getByRole('alertdialog', { name: 'Confirm action' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm' })).toHaveFocus();

    await user.tab();
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Confirm' })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
