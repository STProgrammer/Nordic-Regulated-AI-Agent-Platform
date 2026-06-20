'use client';

import { useTranslations } from 'next-intl';

import { ProtectedPage } from '@/components/auth/protected-page';
import { Card } from '@/components/ui/card';

export type PlaceholderArea = 'cases' | 'approvals' | 'evaluations' | 'admin' | 'audit';

export function PlaceholderPage({ area }: { area: PlaceholderArea }) {
  const t = useTranslations(`placeholder.${area}`);

  return (
    <ProtectedPage>
      <Card>
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-3 max-w-2xl text-slate-700">{t('description')}</p>
      </Card>
    </ProtectedPage>
  );
}
