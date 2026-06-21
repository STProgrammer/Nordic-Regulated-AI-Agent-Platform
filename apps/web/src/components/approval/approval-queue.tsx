'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';

import { ProtectedPage } from '@/components/auth/protected-page';
import { Alert } from '@/components/ui/alert';
import type { AppLocale } from '@/i18n/routing';
import { useApprovalQueue } from '@/lib/approvals/query';
import { useCurrentUser } from '@/lib/auth/query';

const reviewerRoles = new Set(['Admin', 'Compliance Reviewer']);

/** Protected queue page; all decision authority remains enforced by the API service. */
export function ApprovalQueue() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('approvals');
  const user = useCurrentUser();
  const queue = useApprovalQueue();
  const canReview = user.data?.roles.some((role) => reviewerRoles.has(role)) ?? false;

  return (
    <ProtectedPage>
      <main className="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('title')}</h1>
          <p className="mt-2 text-slate-700">{t('description')}</p>
        </div>
        {!canReview && user.data ? <Alert>{t('unavailableForRole')}</Alert> : null}
        {queue.isPending ? (
          <p aria-live="polite" role="status">
            {t('loading')}
          </p>
        ) : null}
        {queue.isError ? <Alert>{t('unavailable')}</Alert> : null}
        {queue.data?.items.length === 0 ? <p className="text-slate-700">{t('empty')}</p> : null}
        {queue.data?.items.length ? (
          <ul aria-label={t('queueLabel')} className="space-y-3">
            {queue.data.items.map((item) => (
              <li
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
                key={item.approval_id}
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-600">{item.case_number}</p>
                    <h2 className="mt-1 text-xl font-semibold">{item.case_title}</h2>
                    <p className="mt-2 text-slate-700">
                      {t(`risk.${item.risk_level}`)} · {t(`status.${item.approval_status}`)}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      {item.assigned_user_id ? t('assigned') : t('unassigned')}
                    </p>
                  </div>
                  {canReview ? (
                    <Link
                      className="inline-flex min-h-10 items-center rounded-md bg-slate-900 px-4 py-2 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                      href={`/${locale}/approvals/${item.approval_id}`}
                    >
                      {t('openPacket')}
                    </Link>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </main>
    </ProtectedPage>
  );
}
