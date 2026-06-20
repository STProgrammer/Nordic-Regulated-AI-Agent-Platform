'use client';

import { useLocale, useTranslations } from 'next-intl';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, type PropsWithChildren } from 'react';

import { ApplicationShell } from '@/components/layout/application-shell';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { ApiFailure } from '@/lib/api/contracts';
import { loginPath } from '@/lib/auth/paths';
import { useCurrentUser } from '@/lib/auth/query';

function SessionLoading({ text }: { text: string }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl items-center px-4">
      <p aria-live="polite" role="status">
        {text}
      </p>
    </main>
  );
}

export function ProtectedPage({ children }: PropsWithChildren) {
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const router = useRouter();
  const query = useCurrentUser();
  const tCommon = useTranslations('common');
  const tSession = useTranslations('session');
  const unauthorized = query.error instanceof ApiFailure && [401, 403].includes(query.error.status);

  useEffect(() => {
    if (unauthorized) {
      router.replace(loginPath(locale, pathname));
    }
  }, [locale, pathname, router, unauthorized]);

  if (query.isPending || unauthorized) {
    return <SessionLoading text={unauthorized ? tSession('redirecting') : tCommon('loading')} />;
  }

  if (query.isError || query.data === undefined) {
    return (
      <main className="mx-auto flex min-h-screen max-w-xl items-center px-4">
        <Alert>
          <h1 className="font-semibold">{tSession('unavailableTitle')}</h1>
          <p className="mt-2">{tSession('unavailableDescription')}</p>
          <Button className="mt-4" onClick={() => void query.refetch()}>
            {tCommon('retry')}
          </Button>
        </Alert>
      </main>
    );
  }

  return <ApplicationShell user={query.data}>{children}</ApplicationShell>;
}
