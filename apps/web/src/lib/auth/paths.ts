import type { AppLocale } from '@/i18n/routing';

export function loginPath(locale: AppLocale, returnTo?: string): string {
  const path = `/${locale}/login`;
  return returnTo ? `${path}?returnTo=${encodeURIComponent(returnTo)}` : path;
}

export function safeReturnPath(value: string | null, locale: AppLocale): string {
  if (
    value !== null &&
    value.startsWith(`/${locale}/`) &&
    !value.startsWith('//') &&
    !value.includes('\\')
  ) {
    return value;
  }

  return `/${locale}/cases`;
}
