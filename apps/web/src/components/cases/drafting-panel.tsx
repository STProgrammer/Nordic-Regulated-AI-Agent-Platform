'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { documentsApi } from '@/lib/api/documents';
import { type Draft, type WorkflowRun } from '@/lib/api/contracts';
import { draftingApi } from '@/lib/api/drafting';
import { workflowsApi } from '@/lib/api/workflows';
import { useCurrentUser } from '@/lib/auth/query';

const allowedRoles = new Set(['Admin', 'Compliance Reviewer', 'Case Worker', 'Manager']);
const activeStatuses = new Set(['queued', 'running']);

/** Original AI text stays read-only here; risk, approval, and human edits belong to later phases. */
export function DraftingPanel({ caseId }: { caseId: string }) {
  const t = useTranslations('drafting');
  const locale = useLocale();
  const user = useCurrentUser();
  const queryClient = useQueryClient();
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const canStart = user.data?.roles.some((role) => allowedRoles.has(role)) ?? false;
  const status = useQuery({
    enabled: run !== null && activeStatuses.has(run.status),
    queryFn: () => workflowsApi.get(run?.workflow_run_id ?? ''),
    queryKey: ['drafting-workflow', run?.workflow_run_id],
    refetchInterval: (query) =>
      query.state.data && !activeStatuses.has(query.state.data.status) ? false : 1500,
  });
  const displayedRun = status.data ?? run;
  const draft = useQuery({
    enabled: displayedRun?.status === 'completed',
    queryFn: () => draftingApi.get(caseId),
    queryKey: ['draft', caseId],
  });
  useEffect(() => {
    if (displayedRun?.status === 'completed') {
      void queryClient.invalidateQueries({ queryKey: ['draft', caseId] });
    }
  }, [caseId, displayedRun?.status, queryClient]);
  const start = useMutation({
    mutationFn: () => workflowsApi.startDrafting(caseId, locale === 'en' ? 'en' : 'nb'),
    onSuccess: (nextRun) => {
      setRun(nextRun);
      void queryClient.invalidateQueries({ queryKey: ['draft', caseId] });
    },
  });

  return (
    <section
      aria-labelledby="drafting-title"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold" id="drafting-title">
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
      {start.isError || status.isError || draft.isError ? <Alert>{t('unavailable')}</Alert> : null}
      {displayedRun ? (
        <DraftingResult draft={draft.data} pending={draft.isPending} run={displayedRun} />
      ) : (
        <p className="mt-4 text-slate-700">{t('notStarted')}</p>
      )}
    </section>
  );
}

function DraftingResult({
  draft,
  pending,
  run,
}: {
  draft: Draft | undefined;
  pending: boolean;
  run: WorkflowRun;
}) {
  const t = useTranslations('drafting');
  const [citation, setCitation] = useState<Draft['citations'][number] | null>(null);
  const context = useMutation({
    mutationFn: ({ chunkId, documentId }: { chunkId: string; documentId: string }) =>
      documentsApi.getContext(documentId, chunkId),
  });
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
  if (!draft) return <Alert>{t('unavailable')}</Alert>;
  return (
    <div className="mt-4 space-y-4">
      <Alert>{t('reviewNotice')}</Alert>
      <p role="status">{t('status.completed')}</p>
      <p className="text-sm text-slate-700">{t(`language.${draft.language}`)}</p>
      <article className="whitespace-pre-wrap rounded-lg border border-slate-200 p-4">
        {draft.content}
      </article>
      <div>
        <h3 className="font-semibold">{t('citations')}</h3>
        <ul className="mt-2 flex flex-wrap gap-2">
          {draft.citations.map((item) => (
            <li key={item.citation_label}>
              <Button
                onClick={() => {
                  setCitation(item);
                  void context.mutateAsync({
                    chunkId: item.chunk_id,
                    documentId: item.document_id,
                  });
                }}
                type="button"
              >
                {item.citation_label}
              </Button>
            </li>
          ))}
        </ul>
      </div>
      {citation ? (
        <div
          aria-label={t('contextTitle')}
          aria-modal="true"
          className="rounded-lg border border-slate-300 bg-slate-50 p-4"
          role="dialog"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold">{t('contextTitle')}</h3>
            <Button onClick={() => setCitation(null)} type="button">
              {t('close')}
            </Button>
          </div>
          {context.isPending ? <p className="mt-3">{t('contextLoading')}</p> : null}
          {context.isError ? <Alert>{t('contextUnavailable')}</Alert> : null}
          {context.data ? (
            <p className="mt-3 whitespace-pre-wrap text-slate-800">{context.data.context}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
