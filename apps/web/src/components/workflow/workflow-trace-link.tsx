'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';

import type { AppLocale } from '@/i18n/routing';

/** Link to a separately loaded safe trace, rather than embedding trace data in Case Detail. */
export function WorkflowTraceLink({ workflowRunId }: { workflowRunId: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('workflowTrace');
  return (
    <Link
      className="inline-flex text-sm font-medium text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
      href={`/${locale}/workflows/${encodeURIComponent(workflowRunId)}/trace`}
    >
      {t('openTrace')}
    </Link>
  );
}
