'use client';

import { useLocale, useTranslations } from 'next-intl';

import type { AppLocale } from '@/i18n/routing';
import type { EvaluationMetrics, EvaluationResult } from '@/lib/api/contracts';
import { formatNumber } from '@/lib/formatting';

function formatScore(value: number | null, locale: AppLocale, unavailable: string): string {
  if (value === null) return unavailable;
  return new Intl.NumberFormat(locale === 'nb' ? 'nb-NO' : 'en', {
    maximumFractionDigits: 1,
    style: 'percent',
  }).format(value);
}

export function EvaluationMetrics({ metrics }: { metrics: EvaluationMetrics }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('evaluations');
  const scores: [keyof typeof scoreLabels, number | null][] = [
    ['retrieval', metrics.retrieval_mean],
    ['citation', metrics.citation_mean],
    ['structuralFaithfulness', metrics.structural_faithfulness_mean],
    ['refusal', metrics.refusal_mean],
    ['risk', metrics.risk_mean],
    ['routing', metrics.routing_mean],
  ];
  return (
    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {scores.map(([key, value]) => (
        <MetricValue
          key={key}
          label={t(scoreLabels[key])}
          value={formatScore(value, locale, t('notRecorded'))}
        />
      ))}
      <MetricValue
        label={t('latency')}
        value={
          metrics.average_latency_ms === null
            ? t('notRecorded')
            : `${formatNumber(metrics.average_latency_ms, locale)} ms`
        }
        note={
          metrics.average_latency_ms === null
            ? undefined
            : t('sampleCount', {
                count: formatNumber(metrics.latency_sample_count, locale),
                total: formatNumber(metrics.case_total, locale),
              })
        }
      />
      <MetricValue
        label={t('cost')}
        value={
          metrics.total_cost_estimate === null
            ? t('notRecorded')
            : formatNumber(metrics.total_cost_estimate, locale)
        }
        note={
          metrics.total_cost_estimate === null
            ? undefined
            : t('sampleCount', {
                count: formatNumber(metrics.cost_sample_count, locale),
                total: formatNumber(metrics.case_total, locale),
              })
        }
      />
    </dl>
  );
}

export function EvaluationResultMetrics({ result }: { result: EvaluationResult }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('evaluations');
  const scores: [keyof typeof scoreLabels, number | null][] = [
    ['retrieval', result.retrieval_score],
    ['citation', result.citation_score],
    ['structuralFaithfulness', result.structural_faithfulness_score],
    ['refusal', result.refusal_score],
    ['risk', result.risk_score],
    ['routing', result.routing_score],
  ];
  return (
    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {scores.map(([key, value]) => (
        <MetricValue
          key={key}
          label={t(scoreLabels[key])}
          value={formatScore(value, locale, t('notRecorded'))}
        />
      ))}
      <MetricValue
        label={t('latency')}
        value={
          result.latency_ms === null
            ? t('notRecorded')
            : `${formatNumber(result.latency_ms, locale)} ms`
        }
      />
      <MetricValue
        label={t('cost')}
        value={
          result.cost_estimate === null
            ? t('notRecorded')
            : formatNumber(result.cost_estimate, locale)
        }
      />
    </dl>
  );
}

function MetricValue({
  label,
  note,
  value,
}: {
  label: string;
  note?: string | undefined;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <dt className="text-sm font-medium text-slate-700">{label}</dt>
      <dd className="mt-1 text-lg font-semibold text-slate-950">{value}</dd>
      {note ? <p className="mt-1 text-xs text-slate-600">{note}</p> : null}
    </div>
  );
}

const scoreLabels = {
  citation: 'citation',
  refusal: 'refusal',
  retrieval: 'retrieval',
  risk: 'risk',
  routing: 'routing',
  structuralFaithfulness: 'structuralFaithfulness',
} as const;
