'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { WorkflowTraceLink } from '@/components/workflow/workflow-trace-link';
import { documentsApi } from '@/lib/api/documents';
import {
  type ExtractedField,
  type ExtractedFieldEditInput,
  type ExtractionFieldKind,
  type ExtractionValue,
  type WorkflowRun,
} from '@/lib/api/contracts';
import { extractionApi } from '@/lib/api/extraction';
import { workflowsApi } from '@/lib/api/workflows';
import { useCurrentUser } from '@/lib/auth/query';

const allowedRoles = new Set(['Admin', 'Compliance Reviewer', 'Case Worker', 'Manager']);
const editableRoles = new Set(['Admin', 'Case Worker', 'Manager']);
const activeStatuses = new Set(['queued', 'running']);
const stringKinds = new Set<ExtractionFieldKind>([
  'people',
  'organizations',
  'obligations',
  'tasks',
  'risks',
  'missing_information',
  'suggested_next_actions',
]);

/** Source-linked structured observations only; this panel never implies final risk or advice. */
export function ExtractionPanel({ caseId }: { caseId: string }) {
  const t = useTranslations('extraction');
  const user = useCurrentUser();
  const queryClient = useQueryClient();
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const canStart = user.data?.roles.some((role) => allowedRoles.has(role)) ?? false;
  const canEdit = user.data?.roles.some((role) => editableRoles.has(role)) ?? false;
  const status = useQuery({
    enabled: run !== null && activeStatuses.has(run.status),
    queryFn: () => workflowsApi.get(run?.workflow_run_id ?? ''),
    queryKey: ['extraction-workflow', run?.workflow_run_id],
    refetchInterval: (query) =>
      query.state.data && !activeStatuses.has(query.state.data.status) ? false : 1500,
  });
  const activeRun = status.data ?? run;
  const activeStatus = activeRun?.status;
  useEffect(() => {
    if (activeStatus && !activeStatuses.has(activeStatus)) {
      void queryClient.invalidateQueries({ queryKey: ['extraction-fields', caseId] });
    }
  }, [activeStatus, caseId, queryClient]);
  const fields = useQuery({
    queryFn: () => extractionApi.list(caseId),
    queryKey: ['extraction-fields', caseId],
    refetchInterval: activeStatuses.has(activeRun?.status ?? '') ? 1500 : false,
  });
  const start = useMutation({
    mutationFn: () => workflowsApi.startExtraction(caseId),
    onSuccess: (nextRun) => {
      setRun(nextRun);
      void queryClient.invalidateQueries({ queryKey: ['extraction-fields', caseId] });
    },
  });
  const persistedRun = fields.data?.[0]
    ? {
        workflow_run_id: fields.data[0].workflow_run_id,
        workflow: 'extraction' as const,
        status: 'completed' as const,
        started_at: fields.data[0].updated_at,
        finished_at: fields.data[0].updated_at,
        intake: null,
        evidence: null,
        extraction: null,
      }
    : null;
  const displayedRun = activeRun ?? persistedRun;

  return (
    <section aria-labelledby="extraction-title" className="nordic-surface nordic-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold" id="extraction-title">
            {t('title')}
          </h2>
          <p className="mt-2 text-slate-700">{t('description')}</p>
        </div>
        <Button
          disabled={!canStart || start.isPending || activeStatuses.has(displayedRun?.status ?? '')}
          onClick={() => void start.mutateAsync()}
        >
          {start.isPending ? t('starting') : t('start')}
        </Button>
      </div>
      {!canStart && user.data ? <Alert>{t('unavailableForRole')}</Alert> : null}
      {start.isError || status.isError || fields.isError ? <Alert>{t('unavailable')}</Alert> : null}
      {displayedRun ? (
        <ExtractionResult
          canEdit={canEdit}
          caseId={caseId}
          fields={fields.data ?? []}
          pending={fields.isPending}
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

function ExtractionResult({
  canEdit,
  caseId,
  fields,
  pending,
  run,
}: {
  canEdit: boolean;
  caseId: string;
  fields: ExtractedField[];
  pending: boolean;
  run: WorkflowRun;
}) {
  const t = useTranslations('extraction');
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [contextField, setContextField] = useState<ExtractedField | null>(null);
  const context = useMutation({
    mutationFn: ({ documentId, chunkId }: { documentId: string; chunkId: string }) =>
      documentsApi.getContext(documentId, chunkId),
  });
  const edit = useMutation({
    mutationFn: ({ fieldId, input }: { fieldId: string; input: ExtractedFieldEditInput }) =>
      extractionApi.edit(caseId, fieldId, input),
    onSuccess: () => {
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ['extraction-fields', caseId] });
    },
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
  return (
    <div className="mt-4 space-y-4">
      <p role="status">{t('status.completed')}</p>
      {run.extraction?.low_confidence_field_count ? (
        <Alert>{t('lowConfidenceNotice')}</Alert>
      ) : null}
      {fields.length === 0 ? <p>{t('empty')}</p> : null}
      <ul className="space-y-3">
        {fields.map((field) => (
          <li className="rounded-lg border border-slate-200 p-4" key={field.field_id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">{t(`kinds.${field.field_kind}`)}</h3>
                <FieldValue field={field} />
              </div>
              <div className="flex flex-wrap gap-2">
                {field.source_document_id && field.source_chunk_id ? (
                  <Button
                    onClick={() => {
                      setContextField(field);
                      void context.mutateAsync({
                        documentId: field.source_document_id ?? '',
                        chunkId: field.source_chunk_id ?? '',
                      });
                    }}
                    type="button"
                  >
                    {t('openContext')}
                  </Button>
                ) : null}
                {canEdit ? (
                  <Button onClick={() => setEditing(field.field_id)} type="button">
                    {t('edit')}
                  </Button>
                ) : null}
              </div>
            </div>
            {field.confidence_band === 'low' ? (
              <p className="mt-2 text-amber-800">{t('lowConfidence')}</p>
            ) : null}
            {field.human_edited ? (
              <p className="mt-2 text-emerald-800">{t('humanEdited')}</p>
            ) : null}
            {editing === field.field_id ? (
              <FieldEditForm
                field={field}
                onCancel={() => setEditing(null)}
                onSubmit={(input) => void edit.mutateAsync({ fieldId: field.field_id, input })}
                pending={edit.isPending}
              />
            ) : null}
          </li>
        ))}
      </ul>
      {contextField ? (
        <section
          aria-labelledby="extraction-context-title"
          className="rounded-lg border border-slate-300 bg-slate-50 p-4"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold" id="extraction-context-title">
              {t('contextTitle')}
            </h3>
            <Button onClick={() => setContextField(null)} type="button" variant="secondary">
              {t('close')}
            </Button>
          </div>
          {context.isPending ? <p className="mt-3">{t('contextLoading')}</p> : null}
          {context.isError ? <Alert>{t('contextUnavailable')}</Alert> : null}
          {context.data ? (
            <p className="mt-3 whitespace-pre-wrap text-slate-800">{context.data.context}</p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function FieldValue({ field }: { field: ExtractedField }) {
  const value = field.field_value;
  if ('items' in value)
    return (
      <ul className="mt-2 list-disc pl-5">
        {value.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  if ('dates' in value)
    return (
      <ul className="mt-2 list-disc pl-5">
        {value.dates.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  if ('references' in value)
    return (
      <ul className="mt-2 list-disc pl-5">
        {value.references.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  return (
    <ul className="mt-2 list-disc pl-5">
      {value.amounts.map((item) => (
        <li key={`${item.amount}-${item.currency}`}>
          {item.amount} {item.currency}
          {item.label ? ` — ${item.label}` : ''}
        </li>
      ))}
    </ul>
  );
}

function FieldEditForm({
  field,
  onCancel,
  onSubmit,
  pending,
}: {
  field: ExtractedField;
  onCancel: () => void;
  onSubmit: (input: ExtractedFieldEditInput) => void;
  pending: boolean;
}) {
  const t = useTranslations('extraction');
  const [value, setValue] = useState(editValue(field.field_value));
  return (
    <form
      className="mt-4 space-y-2 border-t border-slate-200 pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        const input = parseEditValue(field.field_kind, value);
        if (input) onSubmit(input);
      }}
    >
      <label className="block font-medium" htmlFor={`field-${field.field_id}`}>
        {t('editLabel')}
      </label>
      <textarea
        className="min-h-24 w-full rounded-md border border-slate-400 bg-white px-3 py-2"
        id={`field-${field.field_id}`}
        onChange={(event) => setValue(event.target.value)}
        value={value}
      />
      <p className="text-sm text-slate-700">
        {field.field_kind === 'amounts' ? t('amountHelp') : t('listHelp')}
      </p>
      <div className="flex gap-2">
        <Button disabled={pending} type="submit">
          {pending ? t('saving') : t('save')}
        </Button>
        <Button onClick={onCancel} type="button">
          {t('cancel')}
        </Button>
      </div>
    </form>
  );
}

function editValue(value: ExtractionValue): string {
  if ('items' in value) return value.items.join('\n');
  if ('dates' in value) return value.dates.join('\n');
  if ('references' in value) return value.references.join('\n');
  return value.amounts
    .map((item) => [item.amount, item.currency, item.label ?? ''].join('|'))
    .join('\n');
}

function parseEditValue(kind: ExtractionFieldKind, value: string): ExtractedFieldEditInput | null {
  const lines = value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) return null;
  if (stringKinds.has(kind)) return { field_value: { items: lines } };
  if (kind === 'dates' || kind === 'deadlines') return { field_value: { dates: lines } };
  if (kind === 'reference_numbers') return { field_value: { references: lines } };
  const amounts = lines.map((line) => {
    const [amount, currency, label] = line.split('|').map((part) => part.trim());
    return { amount: amount ?? '', currency: currency ?? '', label: label || null };
  });
  return { field_value: { amounts } };
}
