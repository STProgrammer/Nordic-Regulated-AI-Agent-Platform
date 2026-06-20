'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useState } from 'react';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { documentsApi } from '@/lib/api/documents';
import { type EvidenceSource, type WorkflowRun } from '@/lib/api/contracts';
import { workflowsApi } from '@/lib/api/workflows';
import { useCurrentUser } from '@/lib/auth/query';

const allowedRoles = new Set(['Admin', 'Compliance Reviewer', 'Case Worker', 'Manager']);
const activeStatuses = new Set(['queued', 'running']);

/** A truthful, read-only Evidence package view. It exposes no query, score, or graph trace. */
export function EvidenceGraphPanel({ caseId }: { caseId: string }) {
  const t = useTranslations('evidenceGraph');
  const user = useCurrentUser();
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const canStart = user.data?.roles.some((role) => allowedRoles.has(role)) ?? false;
  const status = useQuery({
    enabled: run !== null && activeStatuses.has(run.status),
    queryFn: () => workflowsApi.get(run?.workflow_run_id ?? ''),
    queryKey: ['evidence-workflow', run?.workflow_run_id],
    refetchInterval: (query) =>
      query.state.data && !activeStatuses.has(query.state.data.status) ? false : 1500,
  });
  const start = useMutation({
    mutationFn: () => workflowsApi.startEvidence(caseId),
    onSuccess: (nextRun) => setRun(nextRun),
  });
  const activeRun = status.data ?? run;

  return (
    <section
      aria-labelledby="evidence-graph-title"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold" id="evidence-graph-title">
            {t('title')}
          </h2>
          <p className="mt-2 text-slate-700">{t('description')}</p>
        </div>
        <Button
          disabled={!canStart || start.isPending || activeStatuses.has(activeRun?.status ?? '')}
          onClick={() => void start.mutateAsync()}
        >
          {start.isPending ? t('starting') : t('start')}
        </Button>
      </div>
      {!canStart && user.data ? <Alert>{t('unavailableForRole')}</Alert> : null}
      {start.isError || status.isError ? <Alert>{t('unavailable')}</Alert> : null}
      {activeRun ? (
        <EvidenceResult run={activeRun} />
      ) : (
        <p className="mt-4 text-slate-700">{t('notStarted')}</p>
      )}
    </section>
  );
}

function EvidenceResult({ run }: { run: WorkflowRun }) {
  const t = useTranslations('evidenceGraph');
  const [selected, setSelected] = useState<EvidenceSource | null>(null);
  const sourceContext = useMutation({
    mutationFn: ({ documentId, chunkId }: { documentId: string; chunkId: string }) =>
      documentsApi.getContext(documentId, chunkId),
  });
  if (activeStatuses.has(run.status)) {
    return (
      <p className="mt-4" role="status">
        {t(`status.${run.status}`)}
      </p>
    );
  }
  if (run.status === 'failed') return <Alert>{t('status.failed')}</Alert>;
  const evidence = run.evidence;
  if (!evidence) return <Alert>{t('unavailable')}</Alert>;
  const needsMore =
    run.status === 'needs_more_evidence' || evidence.outcome === 'needs_more_evidence';
  return (
    <div className="mt-4 space-y-4">
      <p role="status">{needsMore ? t('status.needs_more_evidence') : t('status.completed')}</p>
      {needsMore ? (
        <Alert>
          <p>{evidence.contradiction_detected ? t('contradiction') : t('insufficient')}</p>
        </Alert>
      ) : null}
      {evidence.sources.length ? (
        <div>
          <h3 className="font-semibold">{t('sources')}</h3>
          <ul className="mt-3 space-y-2">
            {evidence.sources.map((source) => (
              <li
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 p-3"
                key={source.citation_label}
              >
                <span>{source.citation_label}</span>
                <Button
                  onClick={() => {
                    setSelected(source);
                    void sourceContext.mutateAsync({
                      documentId: source.document_id,
                      chunkId: source.chunk_id,
                    });
                  }}
                  type="button"
                >
                  {t('openContext')}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {selected ? (
        <div
          aria-label={t('contextTitle')}
          aria-modal="true"
          className="rounded-lg border border-slate-300 bg-slate-50 p-4"
          role="dialog"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold">{t('contextTitle')}</h3>
            <Button onClick={() => setSelected(null)} type="button">
              {t('close')}
            </Button>
          </div>
          {sourceContext.isPending ? <p className="mt-3">{t('contextLoading')}</p> : null}
          {sourceContext.isError ? <Alert>{t('contextUnavailable')}</Alert> : null}
          {sourceContext.data ? (
            <>
              <p className="mt-3 text-sm text-slate-700">{sourceContext.data.document_title}</p>
              <p className="mt-3 whitespace-pre-wrap text-slate-800">
                {sourceContext.data.context}
              </p>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
