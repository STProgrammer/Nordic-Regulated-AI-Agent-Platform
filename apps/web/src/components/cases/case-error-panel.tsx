'use client';

import { useEffect } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { usePathname, useRouter } from 'next/navigation';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { ApiFailure } from '@/lib/api/contracts';
import { loginPath } from '@/lib/auth/paths';

export function CaseErrorPanel({ error, retry }: { error: unknown; retry: () => void }) {
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const router = useRouter();
  const t = useTranslations('cases');
  const tCommon = useTranslations('common');
  const isNotFound = error instanceof ApiFailure && error.status === 404;
  const isUnauthorized = error instanceof ApiFailure && [401, 403].includes(error.status);

  useEffect(() => {
    if (isUnauthorized) router.replace(loginPath(locale, pathname));
  }, [isUnauthorized, locale, pathname, router]);

  if (isUnauthorized) {
    return <p aria-live="polite">{t('loading')}</p>;
  }

  return (
    <Alert>
      <h2 className="font-semibold">{t(isNotFound ? 'notFoundTitle' : 'unavailableTitle')}</h2>
      <p className="mt-2">{t(isNotFound ? 'notFoundDescription' : 'unavailableDescription')}</p>
      {!isNotFound ? (
        <Button className="mt-4" onClick={retry}>
          {tCommon('retry')}
        </Button>
      ) : null}
    </Alert>
  );
}
