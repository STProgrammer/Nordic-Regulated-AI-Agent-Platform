import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { HorizontalTableScroll } from '@/components/ui/horizontal-table-scroll';

describe('HorizontalTableScroll', () => {
  it('keeps the top and bottom horizontal scrollbars synchronized', () => {
    render(
      <HorizontalTableScroll ariaLabel="Wide table" scrollHint="Scroll horizontally">
        <table>
          <tbody>
            <tr>
              <td>Cell</td>
            </tr>
          </tbody>
        </table>
      </HorizontalTableScroll>,
    );

    const topScrollbar = screen.getByRole('region', { name: 'Scroll horizontally' });
    const viewport = screen.getByRole('region', { name: 'Wide table' });

    fireEvent.scroll(topScrollbar, { target: { scrollLeft: 96 } });
    expect(viewport.scrollLeft).toBe(96);

    fireEvent.scroll(viewport, { target: { scrollLeft: 48 } });
    expect(topScrollbar.scrollLeft).toBe(48);
  });
});
