'use client';

import { useLocale } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import type { AppLocale } from '@/i18n/routing';

export function CasesRedirect() {
  const locale = useLocale() as AppLocale;
  const router = useRouter();

  useEffect(() => {
    router.replace(`/${locale}/cases`);
  }, [locale, router]);

  return <ProtectedPage>{null}</ProtectedPage>;
}
