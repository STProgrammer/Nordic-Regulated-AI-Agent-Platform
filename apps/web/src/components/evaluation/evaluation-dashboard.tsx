'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { EvaluationMetrics } from '@/components/evaluation/evaluation-metrics';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { ApiFailure, type EvaluationRun } from '@/lib/api/contracts';
import { useCurrentUser } from '@/lib/auth/query';
import {
  useEvaluationDatasets,
  useEvaluationRuns,
  useEvaluationStart,
} from '@/lib/evaluations/query';
import { formatNumber, formatTimestamp } from '@/lib/formatting';

const PAGE_SIZE = 25;

export function EvaluationDashboard() {
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const t = useTranslations('evaluations');
  const currentUser = useCurrentUser();
  const isAdmin = currentUser.data?.roles.includes('Admin') ?? false;
  const [offset, setOffset] = useState(0);
  const [selectedDatasetKey, setSelectedDatasetKey] = useState('');
  const datasets = useEvaluationDatasets(isAdmin);
  const runs = useEvaluationRuns({ enabled: isAdmin, limit: PAGE_SIZE, offset });
  const start = useEvaluationStart();
  const selectedDataset = selectedDatasetKey || datasets.data?.items[0]?.dataset_key || '';
  const activeSelectedRun = runs.data?.items.some(
    (item) =>
      item.dataset_key === selectedDataset &&
      (item.status === 'queued' || item.status === 'running'),
  );

  async function startEvaluation() {
    if (!selectedDataset) return;
    try {
      const run = await start.mutateAsync(selectedDataset);
      router.push(`/${locale}/evaluations/runs/${run.evaluation_run_id}`);
    } catch {
      // The accessible error state below intentionally keeps error content bounded.
    }
  }

  return (
    <ProtectedPage>
      <main className="mx-auto max-w-6xl space-y-6" data-testid="evaluation-dashboard">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">{t('title')}</h1>
            <p className="mt-2 max-w-3xl text-slate-700">{t('description')}</p>
          </div>
        </header>
        {!isAdmin && currentUser.data ? <Alert>{t('denied')}</Alert> : null}
        {isAdmin ? (
          <>
            <p className="rounded-md border border-sky-200 bg-sky-50 p-4 text-sm text-slate-800">
              {t('structuralFaithfulnessNote')}
            </p>
            <section className="nordic-surface rounded-xl p-5">
              <label
                className="block text-sm font-medium text-slate-800"
                htmlFor="evaluation-dataset"
              >
                {t('dataset')}
              </label>
              <div className="mt-2 flex flex-wrap items-end gap-3">
                <select
                  aria-label={t('dataset')}
                  className="min-h-10 rounded-md border border-slate-300 bg-white px-3 text-slate-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                  disabled={datasets.isPending || !datasets.data?.items.length || start.isPending}
                  id="evaluation-dataset"
                  onChange={(event) => setSelectedDatasetKey(event.target.value)}
                  value={selectedDataset}
                >
                  {datasets.data?.items.map((dataset) => (
                    <option key={dataset.dataset_key} value={dataset.dataset_key}>
                      {dataset.dataset_key} · {dataset.version}
                    </option>
                  ))}
                </select>
                <Button
                  disabled={!selectedDataset || start.isPending || activeSelectedRun}
                  onClick={() => void startEvaluation()}
                >
                  {start.isPending ? t('starting') : t('runEvaluation')}
                </Button>
              </div>
              {start.error instanceof ApiFailure && start.error.status === 409 ? (
                <p className="mt-3 text-sm text-amber-800" role="status">
                  {t('activeRun')}
                </p>
              ) : null}
              {(datasets.isError || start.isError) &&
              !(start.error instanceof ApiFailure && start.error.status === 409) ? (
                <Alert>{t('unavailable')}</Alert>
              ) : null}
            </section>
            {runs.isPending ? (
              <p aria-live="polite" role="status">
                {t('loading')}
              </p>
            ) : null}
            {runs.isError ? (
              <Alert>
                <p>{t('unavailable')}</p>
                <Button className="mt-3" onClick={() => void runs.refetch()}>
                  {t('retry')}
                </Button>
              </Alert>
            ) : null}
            {runs.data ? (
              <DashboardContent
                locale={locale}
                offset={offset}
                onPage={setOffset}
                runs={runs.data}
              />
            ) : null}
          </>
        ) : null}
      </main>
    </ProtectedPage>
  );
}

function DashboardContent({
  locale,
  offset,
  onPage,
  runs,
}: {
  locale: AppLocale;
  offset: number;
  onPage: (offset: number) => void;
  runs: { has_more: boolean; items: EvaluationRun[]; total: number };
}) {
  const t = useTranslations('evaluations');
  const latest = runs.items[0];
  return (
    <>
      {latest ? (
        <section aria-labelledby="latest-evaluation-run" className="nordic-surface nordic-card">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold" id="latest-evaluation-run">
                {t('latestRun')}
              </h2>
              <p className="mt-1 text-sm text-slate-700">
                {t(`statusValue.${latest.status}`)} · {t(`passFailValue.${latest.pass_fail}`)}
              </p>
            </div>
            <Link
              className="inline-flex min-h-10 items-center rounded-md bg-slate-900 px-4 py-2 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
              href={`/${locale}/evaluations/runs/${latest.evaluation_run_id}`}
            >
              {t('viewRun')}
            </Link>
          </div>
          <p className="mt-3 text-sm text-slate-700">
            {t('startedAt')}: {formatTimestamp(latest.started_at, locale)}
          </p>
          <div className="mt-5">
            <EvaluationMetrics metrics={latest.metrics} />
          </div>
        </section>
      ) : (
        <p className="nordic-surface nordic-card text-slate-700">{t('empty')}</p>
      )}
      <section aria-labelledby="recent-evaluation-runs" className="nordic-surface nordic-card">
        <h2 className="text-xl font-semibold" id="recent-evaluation-runs">
          {t('recentRuns')}
        </h2>
        {runs.items.length ? (
          <div className="nordic-table-scroll-window mt-4">
            <table className="nordic-table min-w-[48rem] text-left">
              <thead className="border-b border-slate-200 text-sm text-slate-700">
                <tr>
                  <th className="px-3 py-2" scope="col">
                    {t('status')}
                  </th>
                  <th className="px-3 py-2" scope="col">
                    {t('caseTotal')}
                  </th>
                  <th className="px-3 py-2" scope="col">
                    {t('failedCases')}
                  </th>
                  <th className="px-3 py-2" scope="col">
                    {t('startedAt')}
                  </th>
                  <th className="px-3 py-2" scope="col">
                    <span className="sr-only">{t('viewRun')}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {runs.items.map((run) => (
                  <tr className="border-b border-slate-100" key={run.evaluation_run_id}>
                    <td className="px-3 py-3">{t(`statusValue.${run.status}`)}</td>
                    <td className="px-3 py-3">{formatNumber(run.metrics.case_total, locale)}</td>
                    <td className="px-3 py-3">
                      {formatNumber(run.metrics.failed_case_total, locale)}
                    </td>
                    <td className="px-3 py-3">{formatTimestamp(run.started_at, locale)}</td>
                    <td className="px-3 py-3 text-right">
                      <Link
                        className="text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                        href={`/${locale}/evaluations/runs/${run.evaluation_run_id}`}
                      >
                        {t('viewRun')}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {runs.total > PAGE_SIZE ? (
          <nav aria-label={t('recentRuns')} className="mt-4 flex items-center gap-3">
            <Button disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - PAGE_SIZE))}>
              {t('previous')}
            </Button>
            <span>{t('page', { page: Math.floor(offset / PAGE_SIZE) + 1 })}</span>
            <Button disabled={!runs.has_more} onClick={() => onPage(offset + PAGE_SIZE)}>
              {t('next')}
            </Button>
          </nav>
        ) : null}
      </section>
    </>
  );
}
