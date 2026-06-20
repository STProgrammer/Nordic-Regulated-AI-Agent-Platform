'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useSearchParams } from 'next/navigation';
import type { ReactNode } from 'react';

import { CaseErrorPanel } from '@/components/cases/case-error-panel';
import { PriorityBadge, RiskBadge, StatusBadge } from '@/components/cases/case-badge';
import { ProtectedPage } from '@/components/auth/protected-page';
import { DocumentsSection } from '@/components/documents/documents-section';
import { EvidencePanel } from '@/components/evidence/evidence-panel';
import { IntakePanel } from '@/components/cases/intake-panel';
import { Alert } from '@/components/ui/alert';
import type { AppLocale } from '@/i18n/routing';
import { type CaseDetail as CaseDetailData } from '@/lib/api/contracts';
import { caseFiltersFromSearchParams, caseFiltersToSearchParams } from '@/lib/cases/filters';
import { domainMessageKey, languageMessageKey } from '@/lib/cases/labels';
import { useCaseAssignees, useCaseDetail } from '@/lib/cases/query';
import { formatCalendarDate, formatTimestamp } from '@/lib/formatting';

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function CaseDetail({ caseId }: { caseId: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('cases');
  const searchParams = useSearchParams();
  const validId = uuidPattern.test(caseId);
  const detail = useCaseDetail(caseId, validId);
  const assignees = useCaseAssignees();
  const query = caseFiltersToSearchParams(
    caseFiltersFromSearchParams(new URLSearchParams(searchParams.toString())),
  ).toString();
  const inboxHref = `/${locale}/cases${query ? `?${query}` : ''}`;
  if (!validId)
    return (
      <ProtectedPage>
        <Alert>
          <h1 className="font-semibold">{t('invalidLinkTitle')}</h1>
          <p className="mt-2">{t('invalidLinkDescription')}</p>
        </Alert>
      </ProtectedPage>
    );
  return (
    <ProtectedPage>
      <div className="space-y-6">
        <Link
          className="inline-flex text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
          href={inboxHref}
        >
          {t('backToInbox')}
        </Link>
        {detail.isPending ? (
          <p aria-live="polite" role="status">
            {t('loading')}
          </p>
        ) : null}
        {detail.isError ? (
          <CaseErrorPanel error={detail.error} retry={() => void detail.refetch()} />
        ) : null}
        {detail.data ? (
          <DetailContent
            assignees={assignees.data?.items ?? []}
            caseData={detail.data}
            locale={locale}
          />
        ) : null}
      </div>
    </ProtectedPage>
  );
}

function DetailContent({
  assignees,
  caseData,
  locale,
}: {
  assignees: { display_name: string; user_id: string }[];
  caseData: CaseDetailData;
  locale: AppLocale;
}) {
  const t = useTranslations('cases');
  const assignedName = caseData.assigned_user_id
    ? (assignees.find((option) => option.user_id === caseData.assigned_user_id)?.display_name ??
      t('identityUnavailable'))
    : t('unassigned');
  const metadata: [string, ReactNode][] = [
    [t('fields.caseNumber'), caseData.case_number],
    [t('fields.title'), caseData.title],
    [t('status'), <StatusBadge key="status" value={caseData.status} />],
    [t('fields.domain'), t(domainMessageKey[caseData.domain])],
    [t('fields.caseType'), caseData.case_type ?? t('identityUnavailable')],
    [t('priority'), <PriorityBadge key="priority" value={caseData.priority} />],
    [t('fields.language'), t(languageMessageKey[caseData.language])],
    [t('risk'), <RiskBadge key="risk" value={caseData.risk_level} />],
    [t('assignee'), assignedName],
    [t('fields.submittedBy'), t('identityUnavailable')],
    [
      t('dueDate'),
      caseData.due_date ? (
        <time dateTime={caseData.due_date}>{formatCalendarDate(caseData.due_date, locale)}</time>
      ) : (
        t('noDueDate')
      ),
    ],
    [t('fields.externalReferenceDetail'), caseData.external_reference ?? t('identityUnavailable')],
    [
      t('fields.created'),
      <time dateTime={caseData.inserted_at}>{formatTimestamp(caseData.inserted_at, locale)}</time>,
    ],
    [
      t('fields.updated'),
      <time dateTime={caseData.updated_at}>{formatTimestamp(caseData.updated_at, locale)}</time>,
    ],
  ];
  const futureKeys = ['fields', 'risk', 'approval', 'audit'] as const;
  return (
    <section aria-labelledby="case-detail-title" className="space-y-6">
      <div>
        <p className="text-sm font-medium text-slate-600">{caseData.case_number}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" id="case-detail-title">
          {caseData.title}
        </h1>
      </div>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">{t('fields.description')}</h2>
        <p className="mt-3 whitespace-pre-wrap text-slate-800">{caseData.description}</p>
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">{t('title')}</h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          {metadata.map(([term, description]) => (
            <div key={term}>
              <dt className="text-sm font-medium text-slate-600">{term}</dt>
              <dd className="mt-1">{description}</dd>
            </div>
          ))}
        </dl>
      </section>
      <DocumentsSection caseId={caseData.case_id} />
      <EvidencePanel caseId={caseData.case_id} />
      <IntakePanel caseId={caseData.case_id} />
      <div className="grid gap-4 md:grid-cols-2">
        {futureKeys.map((key) => (
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" key={key}>
            <h2 className="font-semibold">{t(`futureTitles.${key}`)}</h2>
            <p className="mt-2 text-slate-700">{t(`future.${key}`)}</p>
          </section>
        ))}
      </div>
    </section>
  );
}
