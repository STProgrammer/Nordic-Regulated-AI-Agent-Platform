import type { AppLocale } from '@/i18n/routing';

const intlLocales: Record<AppLocale, string> = {
  en: 'en',
  nb: 'nb-NO',
};

export function toIntlLocale(locale: AppLocale): string {
  return intlLocales[locale];
}

export function formatDate(value: Date | number, locale: AppLocale): string {
  return new Intl.DateTimeFormat(toIntlLocale(locale)).format(value);
}

/** Format a server calendar date without turning it into a timezone-sensitive instant. */
export function formatCalendarDate(value: string, locale: AppLocale): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  return new Intl.DateTimeFormat(toIntlLocale(locale), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(Number(year), Number(month) - 1, Number(day))));
}

/** Format an ISO instant as localised date and time after validating it at the API boundary. */
export function formatTimestamp(value: string, locale: AppLocale): string {
  return new Intl.DateTimeFormat(toIntlLocale(locale), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function formatNumber(value: number, locale: AppLocale): string {
  return new Intl.NumberFormat(toIntlLocale(locale)).format(value);
}

export function formatFileSize(value: number, locale: AppLocale): string {
  if (value < 1_024) return `${formatNumber(value, locale)} B`;
  if (value < 1_024 * 1_024) return `${formatNumber(value / 1_024, locale)} KiB`;
  return `${formatNumber(value / (1_024 * 1_024), locale)} MiB`;
}

export function formatCurrency(value: number, locale: AppLocale, currency = 'NOK'): string {
  return new Intl.NumberFormat(toIntlLocale(locale), {
    currency,
    style: 'currency',
  }).format(value);
}
