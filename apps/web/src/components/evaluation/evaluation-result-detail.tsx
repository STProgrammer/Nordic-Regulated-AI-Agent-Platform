'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';

import { ProtectedPage } from '@/components/auth/protected-page';
import { EvaluationResultMetrics } from '@/components/evaluation/evaluation-metrics';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { useEvaluationResult } from '@/lib/evaluations/query';

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function EvaluationResultDetail({
  evaluationResultId,
  evaluationRunId,
}: {
  evaluationResultId: string;
  evaluationRunId: string;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('evaluations');
  const validIds = uuidPattern.test(evaluationRunId) && uuidPattern.test(evaluationResultId);
  const result = useEvaluationResult(evaluationRunId, evaluationResultId, validIds);

  if (!validIds) {
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
      <main className="mx-auto max-w-5xl space-y-6" data-testid="evaluation-result-detail">
        <Link
          className="inline-flex text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
          href={`/${locale}/evaluations/runs/${evaluationRunId}`}
        >
          {t('backToDashboard')}
        </Link>
        {result.isPending ? (
          <p aria-live="polite" role="status">
            {t('loading')}
          </p>
        ) : null}
        {result.isError ? (
          <Alert>
            <p>{t('resultUnavailable')}</p>
            <Button className="mt-3" onClick={() => void result.refetch()}>
              {t('retry')}
            </Button>
          </Alert>
        ) : null}
        {result.data ? (
          <>
            <header>
              <h1 className="text-3xl font-semibold tracking-tight">{t('resultDetail')}</h1>
              <p className="mt-2 text-slate-700">{result.data.case_key}</p>
            </header>
            <section className="nordic-surface nordic-card">
              <dl className="grid gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-sm font-medium text-slate-700">{t('caseKey')}</dt>
                  <dd className="mt-1 text-slate-950">{result.data.case_key}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-slate-700">{t('passFail')}</dt>
                  <dd className="mt-1 text-slate-950">
                    {result.data.passed ? t('passed') : t('failed')}
                  </dd>
                </div>
              </dl>
            </section>
            <section className="nordic-surface nordic-card">
              <h2 className="text-xl font-semibold">{t('title')}</h2>
              <div className="mt-4">
                <EvaluationResultMetrics result={result.data} />
              </div>
            </section>
            <section className="nordic-surface nordic-card">
              <h2 className="text-xl font-semibold">{t('failureCodes')}</h2>
              {result.data.failure_codes.length ? (
                <ul className="mt-3 list-disc space-y-1 pl-5">
                  {result.data.failure_codes.map((code) => (
                    <li key={code}>{code}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-slate-700">{t('noFailureCodes')}</p>
              )}
            </section>
          </>
        ) : null}
      </main>
    </ProtectedPage>
  );
}
