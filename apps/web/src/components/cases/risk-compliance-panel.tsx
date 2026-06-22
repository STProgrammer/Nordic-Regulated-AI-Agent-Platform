'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { WorkflowTraceLink } from '@/components/workflow/workflow-trace-link';
import { type RiskAssessment, type RiskReasonCode, type WorkflowRun } from '@/lib/api/contracts';
import { riskApi } from '@/lib/api/risk';
import { workflowsApi } from '@/lib/api/workflows';
import { useCurrentUser } from '@/lib/auth/query';

const allowedRoles = new Set(['Admin', 'Compliance Reviewer', 'Case Worker', 'Manager']);
const activeStatuses = new Set(['queued', 'running']);
const reasonKeys: Record<RiskReasonCode, `reason.${RiskReasonCode}`> = {
  contradictory_evidence: 'reason.contradictory_evidence',
  high_impact_action: 'reason.high_impact_action',
  low_confidence: 'reason.low_confidence',
  missing_required_source: 'reason.missing_required_source',
  pii_detected: 'reason.pii_detected',
  policy_conflict: 'reason.policy_conflict',
  prompt_injection_detected: 'reason.prompt_injection_detected',
  sensitive_domain: 'reason.sensitive_domain',
  weak_evidence: 'reason.weak_evidence',
};

/** A routing assessment only: no reviewer decision, override, or trace control appears here. */
export function RiskCompliancePanel({ caseId }: { caseId: string }) {
  const t = useTranslations('riskCompliance');
  const user = useCurrentUser();
  const queryClient = useQueryClient();
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const canStart = user.data?.roles.some((role) => allowedRoles.has(role)) ?? false;
  const status = useQuery({
    enabled: run !== null && activeStatuses.has(run.status),
    queryFn: () => workflowsApi.get(run?.workflow_run_id ?? ''),
    queryKey: ['risk-compliance-workflow', run?.workflow_run_id],
    refetchInterval: (query) =>
      query.state.data && !activeStatuses.has(query.state.data.status) ? false : 1500,
  });
  const displayedRun = status.data ?? run;
  const assessment = useQuery({
    enabled: displayedRun?.status === 'completed',
    queryFn: () => riskApi.get(caseId),
    queryKey: ['risk-assessment', caseId],
  });
  useEffect(() => {
    if (displayedRun?.status === 'completed') {
      void queryClient.invalidateQueries({ queryKey: ['risk-assessment', caseId] });
    }
  }, [caseId, displayedRun?.status, queryClient]);
  const start = useMutation({
    mutationFn: () => workflowsApi.startRiskCompliance(caseId),
    onSuccess: (nextRun) => {
      setRun(nextRun);
      void queryClient.invalidateQueries({ queryKey: ['risk-assessment', caseId] });
    },
  });

  return (
    <section aria-labelledby="risk-compliance-title" className="nordic-surface nordic-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold" id="risk-compliance-title">
            {t('title')}
          </h2>
          <p className="mt-2 text-slate-700">{t('description')}</p>
        </div>
        <Button
          disabled={!canStart || start.isPending || activeStatuses.has(displayedRun?.status ?? '')}
          onClick={() => void start.mutateAsync()}
          type="button"
        >
          {start.isPending ? t('starting') : t('start')}
        </Button>
      </div>
      {!canStart && user.data ? <Alert>{t('unavailableForRole')}</Alert> : null}
      {start.isError || status.isError || assessment.isError ? (
        <Alert>{t('unavailable')}</Alert>
      ) : null}
      {displayedRun ? (
        <RiskResult
          assessment={assessment.data}
          pending={assessment.isPending}
          run={displayedRun}
        />
      ) : (
        <p className="mt-4 text-slate-700">{t('notStarted')}</p>
      )}
      {displayedRun ? (
        <p className="mt-4">
          <WorkflowTraceLink workflowRunId={displayedRun.workflow_run_id} />
        </p>
      ) : null}
    </section>
  );
}

function RiskResult({
  assessment,
  pending,
  run,
}: {
  assessment: RiskAssessment | undefined;
  pending: boolean;
  run: WorkflowRun;
}) {
  const t = useTranslations('riskCompliance');
  if (activeStatuses.has(run.status)) {
    return (
      <p className="mt-4" role="status">
        {t(`status.${run.status}`)}
      </p>
    );
  }
  if (run.status === 'needs_more_evidence') return <Alert>{t('status.needs_more_evidence')}</Alert>;
  if (run.status === 'failed') return <Alert>{t('status.failed')}</Alert>;
  if (pending)
    return (
      <p className="mt-4" role="status">
        {t('loading')}
      </p>
    );
  if (!assessment || assessment.workflow_run_id !== run.workflow_run_id)
    return <Alert>{t('unavailable')}</Alert>;
  return (
    <div className="mt-4 space-y-4">
      <p role="status">{t('status.completed')}</p>
      <dl className="grid gap-2 sm:grid-cols-2">
        <div>
          <dt className="font-semibold">{t('riskLevel')}</dt>
          <dd>{t(`level.${assessment.risk_level}`)}</dd>
        </div>
        <div>
          <dt className="font-semibold">{t('nextState')}</dt>
          <dd>{t(`next.${assessment.safe_next_state}`)}</dd>
        </div>
      </dl>
      <div>
        <h3 className="font-semibold">{t('reasons')}</h3>
        {assessment.risk_reasons.length ? (
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {assessment.risk_reasons.map((reason) => (
              <li key={reason}>{t(reasonKeys[reason])}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-slate-700">{t('noReasons')}</p>
        )}
      </div>
      {assessment.requires_approval ? <Alert>{t('reviewRequired')}</Alert> : null}
    </div>
  );
}
