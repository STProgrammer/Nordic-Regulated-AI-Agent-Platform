import { describe, expect, it } from 'vitest';

import { formatCalendarDate, formatCurrency, formatNumber } from '@/lib/formatting';

describe('localized formatting', () => {
  it('uses Norwegian Bokmål date, number, and currency conventions', () => {
    expect(formatCalendarDate('2025-01-15', 'nb')).toBe('15. januar 2025');
    expect(formatNumber(1234567.89, 'nb')).toBe('1\u00a0234\u00a0567,89');
    expect(formatCurrency(1234.5, 'nb')).toBe('1\u00a0234,50\u00a0kr');
  });

  it('uses English date, number, and currency conventions after a locale switch', () => {
    expect(formatCalendarDate('2025-01-15', 'en')).toBe('January 15, 2025');
    expect(formatNumber(1234567.89, 'en')).toBe('1,234,567.89');
    expect(formatCurrency(1234.5, 'en')).toBe('NOK\u00a01,234.50');
  });
});
