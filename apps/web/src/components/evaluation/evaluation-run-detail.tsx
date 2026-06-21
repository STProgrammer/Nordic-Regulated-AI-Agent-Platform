'use client';

import { useMutation } from '@tanstack/react-query';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';

import { ProtectedPage } from '@/components/auth/protected-page';
import { EvaluationMetrics } from '@/components/evaluation/evaluation-metrics';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { evaluationsApi } from '@/lib/api/evaluations';
import { useEvaluationRun } from '@/lib/evaluations/query';
import { formatNumber, formatTimestamp } from '@/lib/formatting';

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function EvaluationRunDetail({ evaluationRunId }: { evaluationRunId: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('evaluations');
  const validId = uuidPattern.test(evaluationRunId);
  const run = useEvaluationRun(evaluationRunId, validId);
  const report = useMutation({
    mutationFn: () => evaluationsApi.exportReport(evaluationRunId, locale),
    onSuccess: (download) => saveReport(download.content, download.filename),
  });

  if (!validId) {
    return (
      <ProtectedPage>
        <Alert>
          <h1 className="font-semibold">{t('invalidLinkTitle')}</h1>
          <p className="mt-2">{t('invalidLinkDescription')}</p>
        </Alert>
      </ProtectedPage>
    );
  }

  return (
    <ProtectedPage>
      <main className="mx-auto max-w-6xl space-y-6" data-testid="evaluation-run-detail">
        <Link
          className="inline-flex text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
          href={`/${locale}/evaluations`}
        >
          {t('backToDashboard')}
        </Link>
        {run.isPending ? (
          <p aria-live="polite" role="status">
            {t('loading')}
          </p>
        ) : null}
        {run.isError ? (
          <Alert>
            <p>{t('runUnavailable')}</p>
            <Button className="mt-3" onClick={() => void run.refetch()}>
              {t('retry')}
            </Button>
          </Alert>
        ) : null}
        {run.data ? (
          <RunContent
            locale={locale}
            onExport={() => void report.mutateAsync()}
            reportError={report.isError}
            reportPending={report.isPending}
            run={run.data}
          />
        ) : null}
      </main>
    </ProtectedPage>
  );
}

function RunContent({
  locale,
  onExport,
  reportError,
  reportPending,
  run: detail,
}: {
  locale: AppLocale;
  onExport: () => void;
  reportError: boolean;
  reportPending: boolean;
  run: Awaited<ReturnType<typeof useEvaluationRun>>['data'];
}) {
  const t = useTranslations('evaluations');
  if (!detail) return null;
  const { run, results } = detail;
  const terminal = run.status === 'completed' || run.status === 'failed';
  return (
    <>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('runDetail')}</h1>
          <p className="mt-2 text-slate-700">
            {t(`statusValue.${run.status}`)} · {t(`passFailValue.${run.pass_fail}`)}
          </p>
        </div>
        {terminal ? (
          <Button
            data-testid="evaluation-report-download"
            disabled={reportPending}
            onClick={onExport}
          >
            {reportPending ? t('downloadingReport') : t('downloadReport')}
          </Button>
        ) : null}
      </header>
      {reportError ? <Alert>{t('reportUnavailable')}</Alert> : null}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <DetailValue label={t('status')} value={t(`statusValue.${run.status}`)} />
          <DetailValue label={t('passFail')} value={t(`passFailValue.${run.pass_fail}`)} />
          <DetailValue label={t('startedAt')} value={formatTimestamp(run.started_at, locale)} />
          <DetailValue
            label={t('finishedAt')}
            value={run.finished_at ? formatTimestamp(run.finished_at, locale) : t('notRecorded')}
          />
          <DetailValue
            label={t('caseTotal')}
            value={formatNumber(run.metrics.case_total, locale)}
          />
          <DetailValue
            label={t('passedCases')}
            value={formatNumber(run.metrics.passed_case_total, locale)}
          />
          <DetailValue
            label={t('failedCases')}
            value={formatNumber(run.metrics.failed_case_total, locale)}
          />
          <DetailValue
            label={t('runFailureCode')}
            value={run.metrics.run_failure_code ?? t('notRecorded')}
          />
        </dl>
      </section>
      <section
        aria-labelledby="evaluation-run-metrics"
        className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 className="text-xl font-semibold" id="evaluation-run-metrics">
          {t('title')}
        </h2>
        <div className="mt-4">
          <EvaluationMetrics metrics={run.metrics} />
        </div>
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">{t('failureCodes')}</h2>
        {run.metrics.failure_code_counts.length ? (
          <ul className="mt-3 list-disc space-y-1 pl-5">
            {run.metrics.failure_code_counts.map((item) => (
              <li key={item.code}>
                {item.code}: {formatNumber(item.count, locale)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-slate-700">{t('noFailureCodes')}</p>
        )}
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">{t('results')}</h2>
        {results.length ? (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left">
              <thead className="border-b border-slate-200 text-sm text-slate-700">
                <tr>
                  <th className="px-3 py-2" scope="col">
                    {t('caseKey')}
                  </th>
                  <th className="px-3 py-2" scope="col">
                    {t('passFail')}
                  </th>
                  <th className="px-3 py-2" scope="col">
                    {t('failureCodes')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr className="border-b border-slate-100" key={result.evaluation_result_id}>
                    <td className="px-3 py-3">
                      {result.passed ? (
                        result.case_key
                      ) : (
                        <Link
                          className="text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                          href={`/${locale}/evaluations/runs/${run.evaluation_run_id}/results/${result.evaluation_result_id}`}
                        >
                          {result.case_key}
                        </Link>
                      )}
                    </td>
                    <td className="px-3 py-3">{result.passed ? t('passed') : t('failed')}</td>
                    <td className="px-3 py-3">
                      {result.failure_codes.join(', ') || t('noFailureCodes')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-3 text-slate-700">{t('empty')}</p>
        )}
      </section>
    </>
  );
}

function DetailValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm font-medium text-slate-700">{label}</dt>
      <dd className="mt-1 text-slate-950">{value}</dd>
    </div>
  );
}

function saveReport(content: string, filename: string): void {
  const objectUrl = URL.createObjectURL(
    new Blob([content], { type: 'text/markdown;charset=utf-8' }),
  );
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}
