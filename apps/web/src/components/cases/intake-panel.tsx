'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { WorkflowTraceLink } from '@/components/workflow/workflow-trace-link';
import type { AppLocale } from '@/i18n/routing';
import { type IntakeCaseType, type WorkflowRun } from '@/lib/api/contracts';
import { workflowsApi } from '@/lib/api/workflows';
import { useCurrentUser } from '@/lib/auth/query';
import { domainMessageKey } from '@/lib/cases/labels';
import { formatTimestamp } from '@/lib/formatting';

const allowedRoles = new Set(['Admin', 'Case Worker', 'Manager']);
const caseTypes: IntakeCaseType[] = [
  'case_support',
  'compliance_review',
  'operational_incident',
  'policy_question',
  'document_intelligence',
  'unknown',
];
const domains = [
  'public_sector',
  'banking_compliance',
  'energy_operations',
  'internal_policy',
] as const;

export function IntakePanel({ caseId }: { caseId: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('intake');
  const user = useCurrentUser();
  const queryClient = useQueryClient();
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const canStart = user.data?.roles.some((role) => allowedRoles.has(role)) ?? false;
  const status = useQuery({
    enabled: run !== null && ['queued', 'running'].includes(run.status),
    queryFn: () => workflowsApi.get(run?.workflow_run_id ?? ''),
    queryKey: ['intake-workflow', run?.workflow_run_id],
    refetchInterval: (query) =>
      query.state.data && ['completed', 'failed'].includes(query.state.data.status) ? false : 1500,
  });
  const activeRun = status.data ?? run;
  const start = useMutation({
    mutationFn: () => workflowsApi.startIntake(caseId),
    onSuccess: (nextRun) => setRun(nextRun),
  });
  const correction = useMutation({
    mutationFn: ({
      caseType,
      domain,
      reason,
    }: {
      caseType: IntakeCaseType;
      domain: (typeof domains)[number];
      reason: string;
    }) =>
      workflowsApi.correct(activeRun?.workflow_run_id ?? '', {
        case_type: caseType,
        domain,
        ...(reason
          ? { reason_code: reason as 'classification_review' | 'domain_review' | 'user_context' }
          : {}),
      }),
    onSuccess: (nextRun) => {
      setRun(nextRun);
      void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
    },
  });

  return (
    <section
      aria-labelledby="intake-title"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold" id="intake-title">
            {t('title')}
          </h2>
          <p className="mt-2 text-slate-700">{t('description')}</p>
        </div>
        <Button
          disabled={
            !canStart || start.isPending || ['queued', 'running'].includes(activeRun?.status ?? '')
          }
          onClick={() => void start.mutateAsync()}
        >
          {start.isPending ? t('starting') : t('start')}
        </Button>
      </div>
      {!canStart && user.data ? (
        <Alert>
          <p>{t('unavailableForRole')}</p>
        </Alert>
      ) : null}
      {start.isError || status.isError ? (
        <Alert>
          <p>{t('unavailable')}</p>
        </Alert>
      ) : null}
      {activeRun ? (
        <IntakeResult run={activeRun} locale={locale} />
      ) : (
        <p className="mt-4 text-slate-700">{t('notStarted')}</p>
      )}
      {activeRun ? (
        <p className="mt-4">
          <WorkflowTraceLink workflowRunId={activeRun.workflow_run_id} />
        </p>
      ) : null}
      {activeRun?.status === 'completed' && activeRun.intake?.low_confidence ? (
        <CorrectionForm
          initialCaseType={activeRun.intake.case_type ?? 'unknown'}
          initialDomain={activeRun.intake.recommended_domain ?? 'public_sector'}
          onSubmit={(input) => void correction.mutateAsync(input)}
          pending={correction.isPending}
        />
      ) : null}
      {correction.isError ? (
        <Alert>
          <p>{t('correctionUnavailable')}</p>
        </Alert>
      ) : null}
      {correction.isSuccess ? (
        <p className="mt-4 text-sm text-emerald-800" role="status">
          {t('correctionSaved')}
        </p>
      ) : null}
    </section>
  );
}

function CorrectionForm({
  initialCaseType,
  initialDomain,
  onSubmit,
  pending,
}: {
  initialCaseType: IntakeCaseType;
  initialDomain: (typeof domains)[number];
  onSubmit: (input: {
    caseType: IntakeCaseType;
    domain: (typeof domains)[number];
    reason: string;
  }) => void;
  pending: boolean;
}) {
  const t = useTranslations('intake');
  const casesT = useTranslations('cases');
  const [caseType, setCaseType] = useState<IntakeCaseType>(initialCaseType);
  const [domain, setDomain] = useState<(typeof domains)[number]>(initialDomain);
  const [reason, setReason] = useState('');
  return (
    <form
      className="mt-6 space-y-3 border-t border-slate-200 pt-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({ caseType, domain, reason });
      }}
    >
      <h3 className="font-semibold">{t('correctionTitle')}</h3>
      <label className="block font-medium" htmlFor="intake-case-type">
        {t('caseType')}
      </label>
      <select
        className="w-full rounded-md border border-slate-400 bg-white px-3 py-2"
        id="intake-case-type"
        onChange={(event) => setCaseType(event.target.value as IntakeCaseType)}
        value={caseType}
      >
        {caseTypes.map((value) => (
          <option key={value} value={value}>
            {t(`caseTypes.${value}`)}
          </option>
        ))}
      </select>
      <label className="block font-medium" htmlFor="intake-domain">
        {t('domain')}
      </label>
      <select
        className="w-full rounded-md border border-slate-400 bg-white px-3 py-2"
        id="intake-domain"
        onChange={(event) => setDomain(event.target.value as (typeof domains)[number])}
        value={domain}
      >
        {domains.map((value) => (
          <option key={value} value={value}>
            {casesT(domainMessageKey[value])}
          </option>
        ))}
      </select>
      <label className="block font-medium" htmlFor="intake-reason">
        {t('reason')}
      </label>
      <select
        className="w-full rounded-md border border-slate-400 bg-white px-3 py-2"
        id="intake-reason"
        onChange={(event) => setReason(event.target.value)}
        value={reason}
      >
        <option value="">{t('reasonNone')}</option>
        <option value="classification_review">{t('reasons.classification_review')}</option>
        <option value="domain_review">{t('reasons.domain_review')}</option>
        <option value="user_context">{t('reasons.user_context')}</option>
      </select>
      <Button disabled={pending} type="submit">
        {pending ? t('saving') : t('saveCorrection')}
      </Button>
    </form>
  );
}

function IntakeResult({ run, locale }: { run: WorkflowRun; locale: AppLocale }) {
  const t = useTranslations('intake');
  const casesT = useTranslations('cases');
  const result = run.intake;
  if (run.status !== 'completed' || !result) {
    const message =
      run.status === 'queued'
        ? t('status.queued')
        : run.status === 'running'
          ? t('status.running')
          : run.status === 'failed'
            ? t('status.failed')
            : t('status.completed');
    return (
      <p className="mt-4" role="status">
        {message}
      </p>
    );
  }
  const rows: [string, string][] = [
    [t('language'), result.detected_language ?? t('unknown')],
    [t('caseType'), result.case_type ? t(`caseTypes.${result.case_type}`) : t('unknown')],
    [
      t('domain'),
      result.recommended_domain
        ? casesT(domainMessageKey[result.recommended_domain])
        : t('unknown'),
    ],
    [
      t('preliminaryRisk'),
      result.preliminary_risk_level
        ? casesT(`riskLabels.${result.preliminary_risk_level}`)
        : t('unknown'),
    ],
    [
      t('signals'),
      result.pii_detected && result.prompt_injection_detected
        ? t('signalsBoth')
        : result.pii_detected
          ? t('signalsPii')
          : result.prompt_injection_detected
            ? t('signalsInjection')
            : t('signalsNone'),
    ],
    [
      t('nextWorkflow'),
      result.suggested_workflow ? t(`suggested.${result.suggested_workflow}`) : t('unknown'),
    ],
    [
      t('classificationSource'),
      result.classification_source === 'human_corrected' ? t('humanCorrected') : t('model'),
    ],
  ];
  return (
    <div className="mt-5">
      <p className="text-sm text-slate-700">
        {t('completedAt', {
          value: run.finished_at ? formatTimestamp(run.finished_at, locale) : '',
        })}
      </p>
      {result.low_confidence ? (
        <Alert>
          <p>{t('lowConfidence')}</p>
        </Alert>
      ) : null}
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">
        {rows.map(([term, value]) => (
          <div key={term}>
            <dt className="text-sm font-medium text-slate-600">{term}</dt>
            <dd className="mt-1">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
