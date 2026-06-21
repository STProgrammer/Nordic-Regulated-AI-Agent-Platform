'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';

import { Alert } from '@/components/ui/alert';
import type { CaseStatus } from '@/lib/api/contracts';
import type { AppLocale } from '@/i18n/routing';

type ApprovalCaseStatus =
  | 'waiting_for_human_review'
  | 'approved'
  | 'rejected'
  | 'needs_more_evidence';

function isApprovalStatus(status: CaseStatus): status is ApprovalCaseStatus {
  return ['waiting_for_human_review', 'approved', 'rejected', 'needs_more_evidence'].includes(
    status,
  );
}

/** Status-only case projection; review packet content remains behind the approvals API. */
export function ApprovalStatusPanel({ status }: { status: CaseStatus }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('approvalPanel');
  if (!isApprovalStatus(status)) return null;
  return (
    <section
      aria-labelledby="approval-status-title"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 className="text-xl font-semibold" id="approval-status-title">
        {t('title')}
      </h2>
      <Alert>
        <p>{t(`status.${status}`)}</p>
      </Alert>
      <Link
        className="mt-4 inline-flex text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
        href={`/${locale}/approvals`}
      >
        {t('openQueue')}
      </Link>
    </section>
  );
}
