'use client';

import { useTranslations } from 'next-intl';
import { useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { HorizontalTableScroll } from '@/components/ui/horizontal-table-scroll';
import type { AppLocale } from '@/i18n/routing';
import type { AuditFilterInput } from '@/lib/api/audit';
import { useAuditEvents } from '@/lib/audit/query';
import { formatTimestamp } from '@/lib/formatting';
import { useLocale } from 'next-intl';

type DraftFilters = {
  caseId: string;
  eventType: string;
  insertedAfter: string;
  insertedBefore: string;
  resourceType: string;
};

const emptyFilters: DraftFilters = {
  caseId: '',
  eventType: '',
  insertedAfter: '',
  insertedBefore: '',
  resourceType: '',
};

export function AuditTrail() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('auditTrail');
  const [draft, setDraft] = useState<DraftFilters>(emptyFilters);
  const [applied, setApplied] = useState<AuditFilterInput>({ limit: 25, offset: 0 });
  const audit = useAuditEvents(applied);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next: AuditFilterInput = {
      limit: 25,
      offset: 0,
    };
    if (draft.caseId.trim()) next.caseId = draft.caseId.trim();
    if (draft.eventType.trim()) next.eventType = draft.eventType.trim();
    if (draft.insertedAfter.trim()) next.insertedAfter = draft.insertedAfter.trim();
    if (draft.insertedBefore.trim()) next.insertedBefore = draft.insertedBefore.trim();
    if (draft.resourceType.trim()) next.resourceType = draft.resourceType.trim();
    setApplied(next);
  };

  const clear = () => {
    setDraft(emptyFilters);
    setApplied({ limit: 25, offset: 0 });
  };

  return (
    <ProtectedPage>
      <div className="space-y-6" data-testid="audit-trail">
        <header>
          <h1 className="text-3xl font-semibold tracking-tight">{t('title')}</h1>
          <p className="mt-2 text-slate-700">{t('description')}</p>
        </header>
        <form className="nordic-surface nordic-card" onSubmit={submit}>
          <h2 className="text-xl font-semibold">{t('filters')}</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <FilterInput
              label={t('caseId')}
              name="caseId"
              onChange={(value) => setDraft({ ...draft, caseId: value })}
              value={draft.caseId}
            />
            <FilterInput
              label={t('eventType')}
              name="eventType"
              onChange={(value) => setDraft({ ...draft, eventType: value })}
              value={draft.eventType}
            />
            <FilterInput
              label={t('resourceType')}
              name="resourceType"
              onChange={(value) => setDraft({ ...draft, resourceType: value })}
              value={draft.resourceType}
            />
            <FilterInput
              help={t('utcHint')}
              label={t('insertedAfter')}
              name="insertedAfter"
              onChange={(value) => setDraft({ ...draft, insertedAfter: value })}
              placeholder="2026-06-21T10:00:00Z"
              value={draft.insertedAfter}
            />
            <FilterInput
              help={t('utcHint')}
              label={t('insertedBefore')}
              name="insertedBefore"
              onChange={(value) => setDraft({ ...draft, insertedBefore: value })}
              placeholder="2026-06-21T11:00:00Z"
              value={draft.insertedBefore}
            />
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <Button type="submit">{t('apply')}</Button>
            <Button onClick={clear} type="button">
              {t('clear')}
            </Button>
          </div>
        </form>
        {audit.isPending ? (
          <p aria-live="polite" role="status">
            {t('loading')}
          </p>
        ) : null}
        {audit.isError ? (
          <Alert>
            <h2 className="font-semibold">{t('unavailableTitle')}</h2>
            <p className="mt-2">{t('unavailableDescription')}</p>
            <Button className="mt-4" onClick={() => void audit.refetch()} type="button">
              {t('retry')}
            </Button>
          </Alert>
        ) : null}
        {audit.data ? (
          <AuditTable
            locale={locale}
            offset={applied.offset ?? 0}
            onPage={(offset) => setApplied({ ...applied, offset })}
          />
        ) : null}
      </div>
    </ProtectedPage>
  );

  function AuditTable({
    locale: tableLocale,
    offset,
    onPage,
  }: {
    locale: AppLocale;
    offset: number;
    onPage: (next: number) => void;
  }) {
    const data = audit.data;
    if (!data) return null;
    return (
      <section className="nordic-surface nordic-card">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="text-xl font-semibold">{t('events')}</h2>
          <p className="text-sm text-slate-700">{t('results', { count: data.total })}</p>
        </div>
        {data.items.length ? (
          <HorizontalTableScroll
            ariaLabel={t('tableCaption')}
            className="mt-4"
            scrollHint={t('tableScrollHint')}
          >
            <table className="nordic-table min-w-[52rem] text-left text-sm">
              <caption className="sr-only">{t('tableCaption')}</caption>
              <thead className="border-b border-slate-200">
                <tr>
                  {[
                    t('timestamp'),
                    t('eventType'),
                    t('resourceType'),
                    t('caseId'),
                    t('metadata'),
                  ].map((heading) => (
                    <th className="px-3 py-2 font-semibold" key={heading} scope="col">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((event) => (
                  <tr className="border-b border-slate-100" key={event.event_id}>
                    <td className="px-3 py-3">{formatTimestamp(event.inserted_at, tableLocale)}</td>
                    <td className="px-3 py-3">{event.event_type}</td>
                    <td className="px-3 py-3">{event.resource_type}</td>
                    <td className="px-3 py-3 break-all">{event.case_id ?? t('notRecorded')}</td>
                    <td className="px-3 py-3">{metadataText(event.metadata)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </HorizontalTableScroll>
        ) : (
          <p className="mt-4">{t('empty')}</p>
        )}
        <div className="mt-5 flex items-center gap-3">
          <Button
            disabled={offset === 0}
            onClick={() => onPage(Math.max(0, offset - data.limit))}
            type="button"
          >
            {t('previous')}
          </Button>
          <p aria-live="polite" role="status">
            {t('page', { page: Math.floor(offset / data.limit) + 1 })}
          </p>
          <Button
            disabled={!data.has_more}
            onClick={() => onPage(offset + data.limit)}
            type="button"
          >
            {t('next')}
          </Button>
        </div>
      </section>
    );
  }
}

function FilterInput({
  help,
  label,
  name,
  onChange,
  placeholder,
  value,
}: {
  help?: string;
  label: string;
  name: string;
  onChange: (value: string) => void;
  placeholder?: string;
  value: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium" htmlFor={`audit-${name}`}>
        {label}
      </label>
      <input
        aria-describedby={help ? `audit-${name}-help` : undefined}
        className="mt-1 w-full rounded-md border border-slate-400 bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
        id={`audit-${name}`}
        name={name}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        value={value}
      />
      {help ? (
        <p className="mt-1 text-sm text-slate-600" id={`audit-${name}-help`}>
          {help}
        </p>
      ) : null}
    </div>
  );
}

function metadataText(metadata: Record<string, unknown>): string {
  const values = Object.entries(metadata).map(
    ([key, value]) =>
      `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`,
  );
  return values.join(' · ') || '—';
}
