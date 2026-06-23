import type { Metadata } from 'next';
import { NextIntlClientProvider, hasLocale } from 'next-intl';
import { getMessages, getTranslations, setRequestLocale } from 'next-intl/server';
import { notFound } from 'next/navigation';
import type { PropsWithChildren } from 'react';

import '@/app/globals.css';
import { QueryProvider } from '@/components/providers/query-provider';
import { routing, type AppLocale } from '@/i18n/routing';

type LocaleLayoutProps = PropsWithChildren<{
  params: Promise<{ locale: string }>;
}>;

export async function generateMetadata({
  params,
}: Omit<LocaleLayoutProps, 'children'>): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    return {};
  }

  const t = await getTranslations({ locale: locale as AppLocale, namespace: 'app' });
  return {
    other: {
      'nordic-app-shell': 'phase-7',
    },
    title: t('name'),
  };
}

export default async function LocaleLayout({ children, params }: LocaleLayoutProps) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale as AppLocale} suppressHydrationWarning>
      <body data-app-shell="nordic-regulated-ai-shell">
        <NextIntlClientProvider messages={messages}>
          <QueryProvider>{children}</QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
