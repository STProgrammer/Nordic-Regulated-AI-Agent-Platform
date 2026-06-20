'use client';

import { useMutation } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useRef, useState } from 'react';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { documentsApi } from '@/lib/api/documents';
import { retrievalApi } from '@/lib/api/retrieval';
import { ApiFailure, type RetrievalSource } from '@/lib/api/contracts';
import { useCurrentUser } from '@/lib/auth/query';
import { useDocumentList } from '@/lib/documents/query';
import { formatNumber } from '@/lib/formatting';

const retrievalRoles = new Set(['Admin', 'Compliance Reviewer', 'Case Worker', 'Manager']);
const restrictedSourceRoles = new Set(['Admin', 'Compliance Reviewer']);

export function EvidencePanel({ caseId }: { caseId: string }) {
  const t = useTranslations('evidence');
  const currentUser = useCurrentUser();
  const documents = useDocumentList(caseId);
  const [query, setQuery] = useState('');
  const [selectedDocumentId, setSelectedDocumentId] = useState('');
  const canSearch = currentUser.data?.roles.some((role) => retrievalRoles.has(role)) ?? false;
  const hasRestrictedEntitlement =
    currentUser.data?.roles.some((role) => restrictedSourceRoles.has(role)) ?? false;
  const search = useMutation({ mutationFn: retrievalApi.search });
  const selectedDocument = documents.data?.items.find(
    (document) => document.document_id === selectedDocumentId,
  );

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSearch || !query.trim()) return;
    await search.mutateAsync({
      case_id: caseId,
      query: query.trim(),
      limit: 10,
      ...(selectedDocument
        ? {
            document_ids: [selectedDocument.document_id],
            source_statuses: [selectedDocument.source_status],
          }
        : {}),
    });
  }

  return (
    <section
      aria-labelledby="evidence-title"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 className="text-xl font-semibold" id="evidence-title">
        {t('title')}
      </h2>
      <p className="mt-2 text-slate-700">{t('description')}</p>
      {!canSearch && currentUser.data ? (
        <Alert>
          <p>{t('unavailableForRole')}</p>
        </Alert>
      ) : null}
      <form className="mt-4 space-y-3" onSubmit={(event) => void submit(event)}>
        <div>
          <label className="block font-medium" htmlFor="evidence-query">
            {t('queryLabel')}
          </label>
          <textarea
            className="mt-1 min-h-24 w-full rounded-md border border-slate-400 bg-white px-3 py-2"
            disabled={!canSearch || search.isPending}
            id="evidence-query"
            maxLength={2000}
            onChange={(event) => setQuery(event.target.value)}
            value={query}
          />
        </div>
        <div>
          <label className="block font-medium" htmlFor="evidence-document">
            {t('documentScopeLabel')}
          </label>
          <select
            className="mt-1 w-full rounded-md border border-slate-400 bg-white px-3 py-2"
            disabled={!canSearch || documents.isPending}
            id="evidence-document"
            onChange={(event) => setSelectedDocumentId(event.target.value)}
            value={selectedDocumentId}
          >
            <option value="">{t('approvedScope')}</option>
            {documents.data?.items.map((document) => {
              const controlled = ['restricted', 'archived'].includes(document.source_status);
              return (
                <option
                  disabled={controlled && !hasRestrictedEntitlement}
                  key={document.document_id}
                  value={document.document_id}
                >
                  {document.title} — {t(`sourceStatuses.${document.source_status}`)}
                </option>
              );
            })}
          </select>
          <p className="mt-1 text-sm text-slate-700">{t('documentScopeHelp')}</p>
        </div>
        <Button disabled={!canSearch || !query.trim() || search.isPending} type="submit">
          {search.isPending ? t('searching') : t('search')}
        </Button>
      </form>
      {search.isError ? (
        <Alert>
          <p>
            {search.error instanceof ApiFailure && search.error.status === 403
              ? t('forbidden')
              : t('unavailable')}
          </p>
        </Alert>
      ) : null}
      {search.data?.length === 0 ? <p className="mt-5 text-slate-700">{t('empty')}</p> : null}
      {search.data?.length ? <EvidenceResults sources={search.data} /> : null}
    </section>
  );
}

function EvidenceResults({ sources }: { sources: RetrievalSource[] }) {
  const t = useTranslations('evidence');
  const [selected, setSelected] = useState<RetrievalSource | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  return (
    <div className="mt-6 space-y-4">
      <h3 className="font-semibold">{t('resultsTitle')}</h3>
      {sources.map((source) => (
        <EvidenceCard
          key={source.chunk_id}
          onOpenContext={(trigger) => {
            opener.current = trigger;
            setSelected(source);
          }}
          source={source}
        />
      ))}
      {selected ? (
        <SourceContextDialog
          onClose={() => setSelected(null)}
          source={selected}
          trigger={opener.current}
        />
      ) : null}
    </div>
  );
}

function EvidenceCard({
  source,
  onOpenContext,
}: {
  source: RetrievalSource;
  onOpenContext: (trigger: HTMLElement) => void;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('evidence');
  const label = sourceLabel(
    source,
    t('page', { page: source.page_number ?? '' }),
    t('section', { section: source.section_title ?? '' }),
  );
  return (
    <article className="rounded-lg border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="font-semibold">{source.document_title}</h4>
          <p className="mt-1 text-sm text-slate-700">{label}</p>
        </div>
        <p className="text-sm text-slate-700">
          {t('rankSignal', { rank: source.rank, score: formatNumber(source.rank_score, locale) })}
        </p>
      </div>
      <p className="mt-3 whitespace-pre-wrap text-slate-800">{source.excerpt}</p>
      <p className="mt-3 text-sm text-slate-700">
        {t('methodsLabel')}:{' '}
        {source.retrieval_methods.map((method) => t(`methods.${method}`)).join(', ')}
      </p>
      <p className="mt-1 text-sm text-slate-700">
        {t('sourceStatusLabel')}: {t(`sourceStatuses.${source.source_status}`)}
      </p>
      {source.warning_codes.map((warning) => (
        <Alert key={warning}>
          <p>{t(`warnings.${warning}`)}</p>
        </Alert>
      ))}
      <Button className="mt-4" onClick={(event) => onOpenContext(event.currentTarget)}>
        {t('openContext')}
      </Button>
    </article>
  );
}

function SourceContextDialog({
  source,
  onClose,
  trigger,
}: {
  source: RetrievalSource;
  onClose: () => void;
  trigger: HTMLElement | null;
}) {
  const t = useTranslations('evidence');
  const closeButton = useRef<HTMLButtonElement>(null);
  const context = useMutation({
    mutationFn: () => documentsApi.getContext(source.document_id, source.chunk_id),
  });
  function close() {
    onClose();
    trigger?.focus();
  }
  useEffect(() => {
    closeButton.current?.focus();
    void context.mutateAsync();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') close();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
  return (
    <div
      aria-labelledby="source-context-title"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4"
      role="dialog"
    >
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-xl font-semibold" id="source-context-title">
            {t('contextTitle')}
          </h3>
          <button
            className="inline-flex min-h-10 items-center justify-center rounded-md bg-white px-4 py-2 font-medium text-slate-900 ring-1 ring-slate-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
            onClick={close}
            ref={closeButton}
            type="button"
          >
            {t('close')}
          </button>
        </div>
        {context.isPending ? (
          <p className="mt-4" role="status">
            {t('contextLoading')}
          </p>
        ) : null}
        {context.isError ? (
          <Alert>
            <p>
              {context.error instanceof ApiFailure && context.error.status === 403
                ? t('contextForbidden')
                : t('contextUnavailable')}
            </p>
          </Alert>
        ) : null}
        {context.data ? (
          <>
            <p className="mt-3 text-sm text-slate-700">
              {context.data.document_title} · {context.data.document_file_type.toUpperCase()}
            </p>
            <p className="mt-4 whitespace-pre-wrap text-slate-800">{context.data.context}</p>
            {context.data.truncated ? (
              <Alert>
                <p>{t('truncated')}</p>
              </Alert>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

export function sourceLabel(
  source: RetrievalSource,
  pageLabel: string,
  sectionLabel: string,
): string {
  const location =
    source.page_number !== null ? pageLabel : source.section_title ? sectionLabel : '';
  return [source.document_title, source.document_file_type.toUpperCase(), location]
    .filter(Boolean)
    .join(' · ');
}
