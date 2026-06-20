import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactElement } from 'react';

import englishMessages from '../../messages/en.json';
import norwegianMessages from '../../messages/nb.json';
import type { AppLocale } from '@/i18n/routing';

export function renderWithProviders(element: ReactElement, locale: AppLocale = 'nb') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  const messages = locale === 'nb' ? norwegianMessages : englishMessages;

  return render(
    <NextIntlClientProvider locale={locale} messages={messages}>
      <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}
