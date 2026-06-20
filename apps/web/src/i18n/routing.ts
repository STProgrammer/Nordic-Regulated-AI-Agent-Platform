import { defineRouting } from 'next-intl/routing';

export const routing = defineRouting({
  defaultLocale: 'nb',
  localePrefix: 'always',
  locales: ['nb', 'en'],
});

export type AppLocale = (typeof routing.locales)[number];
