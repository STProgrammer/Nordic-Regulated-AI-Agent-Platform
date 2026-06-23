'use client';

import { useMutation } from '@tanstack/react-query';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import type { ReactNode } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { HorizontalTableScroll } from '@/components/ui/horizontal-table-scroll';
import type { AppLocale } from '@/i18n/routing';
import { documentsApi } from '@/lib/api/documents';
import type { WorkflowTrace } from '@/lib/api/contracts';
import { useWorkflowTrace } from '@/lib/audit/query';
import { formatCurrency, formatNumber, formatTimestamp } from '@/lib/formatting';

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function WorkflowTrace({ workflowRunId }: { workflowRunId: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('workflowTrace');
  const trace = useWorkflowTrace(workflowRunId, uuidPattern.test(workflowRunId));

  if (!uuidPattern.test(workflowRunId)) {
    return (
      <ProtectedPage>
        <Alert>
          <h1 className="font-semibold">{t('invalidTitle')}</h1>
          <p className="mt-2">{t('invalidDescription')}</p>
        </Alert>
      </ProtectedPage>
    );
  }

  return (
    <ProtectedPage>
      <div className="space-y-6" data-testid="workflow-trace">
        <Link
          className="inline-flex text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
          href={`/${locale}/cases`}
        >
          {t('backToCases')}
        </Link>
        {trace.isPending ? (
          <p aria-live="polite" role="status">
            {t('loading')}
          </p>
        ) : null}
        {trace.isError ? (
          <Alert>
            <h1 className="font-semibold">{t('unavailableTitle')}</h1>
            <p className="mt-2">{t('unavailableDescription')}</p>
            <Button className="mt-4" onClick={() => void trace.refetch()} type="button">
              {t('retry')}
            </Button>
          </Alert>
        ) : null}
        {trace.data ? <TraceContent locale={locale} trace={trace.data} /> : null}
      </div>
    </ProtectedPage>
  );
}

function TraceContent({ locale, trace }: { locale: AppLocale; trace: WorkflowTrace }) {
  const t = useTranslations('workflowTrace');
  const { header } = trace;
  return (
    <>
      <header>
        <p className="text-sm font-medium text-slate-600">{header.workflow_name}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-2 text-slate-700">{t('description')}</p>
      </header>
      <section aria-labelledby="trace-summary" className="nordic-surface nordic-card">
        <h2 className="text-xl font-semibold" id="trace-summary">
          {t('summary')}
        </h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <SummaryValue
            label={t('workflow')}
            value={`${header.workflow_name} · ${header.workflow_version}`}
          />
          <SummaryValue label={t('status')} value={header.status} />
          <SummaryValue label={t('startedAt')} value={formatTimestamp(header.started_at, locale)} />
          <SummaryValue
            label={t('finishedAt')}
            value={
              header.finished_at ? formatTimestamp(header.finished_at, locale) : t('notRecorded')
            }
          />
          <SummaryValue
            label={t('duration')}
            value={
              header.duration_ms === null
                ? t('notRecorded')
                : t('milliseconds', { value: formatNumber(header.duration_ms, locale) })
            }
          />
          <SummaryValue
            label={t('tokens')}
            value={
              header.total_tokens === null
                ? t('notRecorded')
                : formatNumber(header.total_tokens, locale)
            }
          />
          <SummaryValue
            label={t('estimatedCost')}
            value={
              header.total_cost_estimate === null
                ? t('notRecorded')
                : formatCurrency(header.total_cost_estimate, locale)
            }
          />
          <SummaryValue label={t('errorCode')} value={header.final_error_code ?? t('none')} />
        </dl>
      </section>
      <TraceSection title={t('finalState')}>
        <MetadataList emptyMessage={t('finalStateEmpty')} value={trace.final_state} />
      </TraceSection>
      <TraceSection title={t('nodes')}>
        {trace.nodes.length ? (
          <ol className="space-y-3">
            {trace.nodes.map((node) => (
              <li className="rounded-lg border border-slate-200 p-4" key={node.node_run_id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{node.node_name}</h3>
                    <p className="mt-1 text-sm text-slate-700">{node.status}</p>
                  </div>
                  <p className="text-sm text-slate-700">
                    {t('retries', { count: node.retry_count })}
                  </p>
                </div>
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <SummaryValue
                    label={t('startedAt')}
                    value={formatTimestamp(node.started_at, locale)}
                  />
                  <SummaryValue
                    label={t('duration')}
                    value={
                      node.duration_ms === null
                        ? t('notRecorded')
                        : t('milliseconds', { value: formatNumber(node.duration_ms, locale) })
                    }
                  />
                  <SummaryValue label={t('errorCode')} value={node.error_code ?? t('none')} />
                </dl>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <div>
                    <h4 className="font-medium">{t('inputSummary')}</h4>
                    <MetadataList emptyMessage={t('notRecorded')} value={node.input_summary} />
                  </div>
                  <div>
                    <h4 className="font-medium">{t('outputSummary')}</h4>
                    <MetadataList emptyMessage={t('notRecorded')} value={node.output_summary} />
                  </div>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p>{t('noNodes')}</p>
        )}
      </TraceSection>
      <TraceSection title={t('toolCalls')}>
        {trace.tool_calls.length ? (
          <TraceTable
            headings={[t('name'), t('status'), t('duration'), t('retriesLabel'), t('errorCode')]}
          >
            {trace.tool_calls.map((call) => (
              <tr key={call.tool_call_id}>
                <td>{call.tool_name}</td>
                <td>{call.status}</td>
                <td>
                  {call.duration_ms === null
                    ? t('notRecorded')
                    : t('milliseconds', { value: formatNumber(call.duration_ms, locale) })}
                </td>
                <td>{call.retry_count}</td>
                <td>{call.error_code ?? t('none')}</td>
              </tr>
            ))}
          </TraceTable>
        ) : (
          <p>{t('noToolCalls')}</p>
        )}
      </TraceSection>
      <TraceSection title={t('modelCalls')}>
        {trace.model_calls.length ? (
          <TraceTable
            headings={[t('name'), t('status'), t('tokens'), t('estimatedCost'), t('duration')]}
          >
            {trace.model_calls.map((call) => (
              <tr key={call.model_usage_id}>
                <td>
                  {call.provider} · {call.model_name} · {call.operation}
                </td>
                <td>{call.success ? t('succeeded') : t('failed')}</td>
                <td>
                  {call.total_tokens === null
                    ? t('notRecorded')
                    : formatNumber(call.total_tokens, locale)}
                </td>
                <td>
                  {call.estimated_cost === null
                    ? t('notRecorded')
                    : formatCurrency(call.estimated_cost, locale)}
                </td>
                <td>
                  {call.latency_ms === null
                    ? t('notRecorded')
                    : t('milliseconds', { value: formatNumber(call.latency_ms, locale) })}
                </td>
              </tr>
            ))}
          </TraceTable>
        ) : (
          <p>{t('noModelCalls')}</p>
        )}
      </TraceSection>
      <TraceSection title={t('sources')}>
        {trace.sources.length ? <SourceList sources={trace.sources} /> : <p>{t('noSources')}</p>}
        {trace.unavailable_source_count ? (
          <p className="mt-3 text-sm text-slate-700">
            {t('unavailableSources', { count: trace.unavailable_source_count })}
          </p>
        ) : null}
      </TraceSection>
    </>
  );
}

function SourceList({ sources }: { sources: WorkflowTrace['sources'] }) {
  const t = useTranslations('workflowTrace');
  return (
    <ul className="space-y-3">
      {sources.map((source) => (
        <li
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-4"
          key={`${source.document_id}-${source.chunk_id}`}
        >
          <div>
            <p className="font-semibold">{source.citation_label ?? t('notRecorded')}</p>
            <p className="text-sm text-slate-700">
              {t('rank', { value: source.rank ?? 0 })} ·{' '}
              {source.retrieval_method ?? t('notRecorded')}
            </p>
          </div>
          {source.document_id && source.chunk_id ? (
            <SourceContextButton documentId={source.document_id} chunkId={source.chunk_id} />
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function SourceContextButton({ chunkId, documentId }: { chunkId: string; documentId: string }) {
  const t = useTranslations('workflowTrace');
  const context = useMutation({ mutationFn: () => documentsApi.getContext(documentId, chunkId) });
  return (
    <div>
      <Button onClick={() => void context.mutateAsync()} type="button">
        {t('openSourceContext')}
      </Button>
      {context.isPending ? (
        <p aria-live="polite" className="mt-2 text-sm" role="status">
          {t('contextLoading')}
        </p>
      ) : null}
      {context.isError ? (
        <p className="mt-2 text-sm text-slate-700">{t('contextUnavailable')}</p>
      ) : null}
      {context.data ? (
        <div className="mt-3 max-w-xl rounded border border-slate-200 p-3">
          <p className="font-medium">{context.data.document_title}</p>
          <p className="mt-2 whitespace-pre-wrap text-sm">{context.data.context}</p>
        </div>
      ) : null}
    </div>
  );
}

function TraceSection({ children, title }: { children: ReactNode; title: string }) {
  return (
    <section className="nordic-surface nordic-card">
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function TraceTable({ children, headings }: { children: ReactNode; headings: string[] }) {
  const t = useTranslations('workflowTrace');
  return (
    <HorizontalTableScroll ariaLabel={t('tableCaption')} scrollHint={t('tableScrollHint')}>
      <table className="nordic-table min-w-[48rem] text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-700">
          <tr>
            {headings.map((heading) => (
              <th className="px-3 py-2 font-semibold" key={heading} scope="col">
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </HorizontalTableScroll>
  );
}

function SummaryValue({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-sm font-medium text-slate-600">{label}</dt>
      <dd className="mt-1 break-words">{value}</dd>
    </div>
  );
}

function MetadataList({
  emptyMessage,
  value,
}: {
  emptyMessage: string;
  value: Record<string, unknown>;
}) {
  const entries = Object.entries(value);
  if (!entries.length) return <p className="mt-2 text-sm text-slate-700">{emptyMessage}</p>;
  return (
    <dl className="mt-2 space-y-1 text-sm">
      {entries.map(([key, item]) => (
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-3" key={key}>
          <dt className="font-medium text-slate-700">{key}</dt>
          <dd className="break-words">{metadataValue(item)}</dd>
        </div>
      ))}
    </dl>
  );
}

function metadataValue(value: unknown): string {
  if (value === null) return '—';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
    return String(value);
  return JSON.stringify(value);
}
