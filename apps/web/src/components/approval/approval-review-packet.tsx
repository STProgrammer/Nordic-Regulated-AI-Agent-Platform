'use client';

import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { approvalsApi, saveApprovedOutput } from '@/lib/api/approvals';
import type { ApprovedOutputFormat, MockHandoffTarget } from '@/lib/api/contracts';
import { documentsApi } from '@/lib/api/documents';
import { useApprovalActions, useApprovalPacket } from '@/lib/approvals/query';
import { useCurrentUser } from '@/lib/auth/query';
import type { AppLocale } from '@/i18n/routing';

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const reviewerRoles = new Set(['Admin', 'Compliance Reviewer']);
type TerminalAction = 'approve' | 'edit_and_approve' | 'reject' | 'request_more_evidence';
const exportFormats: ApprovedOutputFormat[] = ['json', 'csv', 'markdown', 'pdf'];
const mockHandoffTargets: MockHandoffTarget[] = ['ticket', 'email', 'teams', 'archive'];

export function ApprovalReviewPacket({ approvalId }: { approvalId: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('approvals');
  const validId = uuidPattern.test(approvalId);
  const packet = useApprovalPacket(approvalId, validId);

  return (
    <ProtectedPage>
      <main className="mx-auto max-w-5xl space-y-6">
        <Link
          className="inline-flex text-sky-800 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
          href={`/${locale}/approvals`}
        >
          {t('backToQueue')}
        </Link>
        {!validId ? <Alert>{t('invalidLink')}</Alert> : null}
        {packet.isPending ? (
          <p aria-live="polite" role="status">
            {t('loadingPacket')}
          </p>
        ) : null}
        {packet.isError ? <Alert>{t('packetUnavailable')}</Alert> : null}
        {packet.data ? <PacketContent approvalId={approvalId} /> : null}
      </main>
    </ProtectedPage>
  );
}

function PacketContent({ approvalId }: { approvalId: string }) {
  const t = useTranslations('approvals');
  const packet = useApprovalPacket(approvalId);
  const user = useCurrentUser();
  const actions = useApprovalActions(approvalId);
  const [comment, setComment] = useState('');
  const [finalText, setFinalText] = useState('');
  const [assignee, setAssignee] = useState('');
  const [pendingAction, setPendingAction] = useState<TerminalAction | null>(null);
  const [pendingHandoff, setPendingHandoff] = useState<MockHandoffTarget | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  if (!packet.data) return null;
  const data = packet.data;
  const canReview = user.data?.roles.some((role) => reviewerRoles.has(role)) ?? false;
  const assignedToAnother =
    data.assigned_user_id !== null && data.assigned_user_id !== user.data?.user_id;
  const canAct =
    canReview &&
    !assignedToAnother &&
    data.workflow_status === 'waiting_for_human_review' &&
    data.decision === null;
  const isSubmitting =
    actions.approve.isPending ||
    actions.editAndApprove.isPending ||
    actions.reject.isPending ||
    actions.requestMoreEvidence.isPending ||
    actions.reassign.isPending ||
    actions.mockHandoff.isPending;
  const commentInput = comment.trim() ? { reviewer_comment: comment.trim() } : {};
  const canUseApprovedOutput =
    canReview && data.approval_status === 'approved' && data.workflow_status === 'completed';

  async function submitTerminalAction() {
    if (!pendingAction) return;
    try {
      if (pendingAction === 'approve') await actions.approve.mutateAsync(commentInput);
      if (pendingAction === 'edit_and_approve') {
        await actions.editAndApprove.mutateAsync({ ...commentInput, final_text: finalText.trim() });
      }
      if (pendingAction === 'reject') await actions.reject.mutateAsync(commentInput);
      if (pendingAction === 'request_more_evidence') {
        await actions.requestMoreEvidence.mutateAsync(commentInput);
      }
      setStatusMessage(t('decisionSubmitted'));
      setPendingAction(null);
    } catch {
      setStatusMessage(t('actionUnavailable'));
    }
  }

  async function reassign() {
    if (!uuidPattern.test(assignee)) {
      setStatusMessage(t('assigneeInvalid'));
      return;
    }
    try {
      await actions.reassign.mutateAsync({ assigned_user_id: assignee });
      setStatusMessage(t('reassigned'));
    } catch {
      setStatusMessage(t('actionUnavailable'));
    }
  }

  async function downloadApprovedOutput(exportFormat: ApprovedOutputFormat) {
    try {
      const download = await approvalsApi.exportApprovedOutput(approvalId, exportFormat);
      saveApprovedOutput(download);
      setStatusMessage(t('exportStarted'));
    } catch {
      setStatusMessage(t('exportUnavailable'));
    }
  }

  async function submitMockHandoff() {
    if (!pendingHandoff) return;
    try {
      await actions.mockHandoff.mutateAsync({ target: pendingHandoff });
      setStatusMessage(t('mockHandoffRecorded'));
      setPendingHandoff(null);
    } catch {
      setStatusMessage(t('mockHandoffUnavailable'));
    }
  }

  return (
    <section
      aria-labelledby="approval-packet-title"
      className="space-y-6"
      data-testid="approval-review-packet"
    >
      <div>
        <p className="text-sm font-medium text-slate-600">{data.case_number}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" id="approval-packet-title">
          {data.case_title}
        </h1>
        <p
          aria-live="polite"
          className="mt-2 text-slate-700"
          data-approval-status={data.approval_status}
          data-testid="approval-decision-status"
          role="status"
        >
          {t(`status.${data.approval_status}`)} · {t(`risk.${data.risk_level}`)}
        </p>
      </div>
      {statusMessage ? <Alert tone="success">{statusMessage}</Alert> : null}
      {assignedToAnother ? <Alert tone="warning">{t('assignedToAnother')}</Alert> : null}
      {!canReview && user.data ? <Alert tone="warning">{t('unavailableForRole')}</Alert> : null}
      <section className="nordic-surface nordic-card">
        <h2 className="text-xl font-semibold">{t('riskReasons')}</h2>
        {data.risk_reasons.length ? (
          <ul className="mt-3 list-disc space-y-1 pl-5">
            {data.risk_reasons.map((reason) => (
              <li key={reason}>{t(`reason.${reason}`)}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-slate-700">{t('noReasons')}</p>
        )}
      </section>
      <section className="nordic-surface nordic-card">
        <h2 className="text-xl font-semibold">{t('originalDraft')}</h2>
        <Alert tone="info">
          <p>{t('originalDraftNotice')}</p>
        </Alert>
        <p className="mt-4 whitespace-pre-wrap text-slate-800">{data.ai_draft}</p>
        {data.final_text ? (
          <>
            <h3 className="mt-6 font-semibold">{t('finalText')}</h3>
            <p
              className="mt-2 whitespace-pre-wrap text-slate-800"
              data-testid="approval-final-text"
            >
              {data.final_text}
            </p>
          </>
        ) : null}
      </section>
      <SourceReferences sources={data.sources} title={t('sources')} />
      <section className="nordic-surface nordic-card">
        <h2 className="text-xl font-semibold">{t('extractedFields')}</h2>
        {data.extracted_fields.length ? (
          <ul className="mt-3 space-y-3">
            {data.extracted_fields.map((field) => (
              <li className="rounded-md border border-slate-200 p-3" key={field.field_id}>
                <p className="font-medium">{field.field_kind}</p>
                <pre className="mt-2 overflow-auto whitespace-pre-wrap text-sm text-slate-700">
                  {JSON.stringify(field.field_value, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-slate-700">{t('noExtractedFields')}</p>
        )}
      </section>
      {canUseApprovedOutput ? (
        <section
          className="nordic-surface nordic-card space-y-5"
          data-testid="approved-output-actions"
        >
          <div>
            <h2 className="text-xl font-semibold">{t('approvedOutputTitle')}</h2>
            <p className="mt-2 text-slate-700">{t('approvedOutputDescription')}</p>
          </div>
          <div>
            <h3 className="font-semibold">{t('exportTitle')}</h3>
            <div className="mt-3 flex flex-wrap gap-3">
              {exportFormats.map((exportFormat) => (
                <Button
                  data-testid={`approved-output-download-${exportFormat}`}
                  disabled={isSubmitting}
                  key={exportFormat}
                  onClick={() => void downloadApprovedOutput(exportFormat)}
                >
                  {t(`exportFormat.${exportFormat}`)}
                </Button>
              ))}
            </div>
          </div>
          <div className="border-t border-slate-200 pt-5">
            <h3 className="font-semibold">{t('mockHandoffTitle')}</h3>
            <Alert tone="info">
              <p>{t('mockHandoffNotice')}</p>
            </Alert>
            <div className="mt-3 flex flex-wrap gap-3">
              {mockHandoffTargets.map((target) => (
                <Button
                  data-testid={`mock-handoff-${target}`}
                  disabled={isSubmitting}
                  key={target}
                  onClick={() => setPendingHandoff(target)}
                >
                  {t(`mockHandoffTarget.${target}`)}
                </Button>
              ))}
            </div>
          </div>
        </section>
      ) : null}
      <section className="nordic-surface nordic-card">
        <h2 className="text-xl font-semibold">{t('decisionTitle')}</h2>
        <p className="mt-2 text-slate-700">{t('decisionDescription')}</p>
        {canAct ? (
          <div className="mt-4 space-y-4">
            <label className="block">
              <span className="font-medium">{t('commentLabel')}</span>
              <textarea
                className="nordic-field mt-2 min-h-24 w-full"
                maxLength={2000}
                onChange={(event) => setComment(event.target.value)}
                value={comment}
              />
            </label>
            <label className="block">
              <span className="font-medium">{t('finalTextLabel')}</span>
              <textarea
                className="nordic-field mt-2 min-h-32 w-full"
                data-testid="approval-final-text-input"
                maxLength={20000}
                onChange={(event) => setFinalText(event.target.value)}
                value={finalText}
              />
              <span className="mt-1 block text-sm text-slate-600">{t('finalTextHint')}</span>
            </label>
            <div className="flex flex-wrap gap-3">
              <Button disabled={isSubmitting} onClick={() => setPendingAction('approve')}>
                {t('approve')}
              </Button>
              <Button
                data-testid="approval-edit-and-approve"
                disabled={isSubmitting || !finalText.trim()}
                onClick={() => setPendingAction('edit_and_approve')}
              >
                {t('editAndApprove')}
              </Button>
              <Button disabled={isSubmitting} onClick={() => setPendingAction('reject')}>
                {t('reject')}
              </Button>
              <Button
                disabled={isSubmitting}
                onClick={() => setPendingAction('request_more_evidence')}
              >
                {t('requestMoreEvidence')}
              </Button>
            </div>
            <div className="border-t border-slate-200 pt-4">
              <label className="block" htmlFor="approval-assignee">
                <span className="font-medium">{t('reassignLabel')}</span>
                <input
                  className="nordic-field mt-2 w-full"
                  id="approval-assignee"
                  onChange={(event) => setAssignee(event.target.value)}
                  placeholder={t('reassignPlaceholder')}
                  value={assignee}
                />
              </label>
              <Button className="mt-3" disabled={isSubmitting} onClick={() => void reassign()}>
                {t('reassign')}
              </Button>
            </div>
          </div>
        ) : (
          <Alert>{t('actionsUnavailable')}</Alert>
        )}
      </section>
      {pendingAction ? (
        <Dialog
          description={t(`confirmation.${pendingAction}`)}
          kind="alertdialog"
          onClose={() => setPendingAction(null)}
          testId="approval-decision-confirmation"
          title={t('confirmTitle')}
        >
          <div className="mt-4 flex gap-3">
            <Button
              data-testid="approval-decision-confirm"
              disabled={isSubmitting}
              onClick={() => void submitTerminalAction()}
            >
              {isSubmitting ? t('submitting') : t('confirm')}
            </Button>
            <Button
              disabled={isSubmitting}
              onClick={() => setPendingAction(null)}
              variant="secondary"
            >
              {t('cancel')}
            </Button>
          </div>
        </Dialog>
      ) : null}
      {pendingHandoff ? (
        <Dialog
          description={t('mockHandoffConfirmation', {
            target: t(`mockHandoffTarget.${pendingHandoff}`),
          })}
          kind="alertdialog"
          onClose={() => setPendingHandoff(null)}
          testId="mock-handoff-confirmation"
          title={t('mockHandoffConfirmTitle')}
        >
          <div className="mt-4 flex gap-3">
            <Button
              data-testid="mock-handoff-confirm"
              disabled={isSubmitting}
              onClick={() => void submitMockHandoff()}
            >
              {isSubmitting ? t('submitting') : t('confirm')}
            </Button>
            <Button
              disabled={isSubmitting}
              onClick={() => setPendingHandoff(null)}
              variant="secondary"
            >
              {t('cancel')}
            </Button>
          </div>
        </Dialog>
      ) : null}
    </section>
  );
}

function SourceReferences({
  sources,
  title,
}: {
  sources: { chunk_id: string; citation_label: string; document_id: string }[];
  title: string;
}) {
  const t = useTranslations('approvals');
  const [selected, setSelected] = useState<(typeof sources)[number] | null>(null);
  const context = useMutation({
    mutationFn: ({ documentId, chunkId }: { documentId: string; chunkId: string }) =>
      documentsApi.getContext(documentId, chunkId),
  });
  return (
    <section className="nordic-surface nordic-card">
      <h2 className="text-xl font-semibold">{title}</h2>
      {sources.length ? (
        <ul className="mt-3 space-y-2">
          {sources.map((source) => (
            <li className="flex items-center justify-between gap-3" key={source.citation_label}>
              <span>{source.citation_label}</span>
              <Button
                onClick={() => {
                  setSelected(source);
                  void context.mutateAsync({
                    documentId: source.document_id,
                    chunkId: source.chunk_id,
                  });
                }}
              >
                {t('openContext')}
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-slate-700">{t('noSources')}</p>
      )}
      {selected ? (
        <section
          aria-labelledby="approval-source-context-title"
          className="mt-4 rounded-lg border border-slate-300 bg-slate-50 p-4"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold" id="approval-source-context-title">
              {t('contextTitle')}
            </h3>
            <Button onClick={() => setSelected(null)} variant="secondary">
              {t('close')}
            </Button>
          </div>
          {context.isPending ? <p className="mt-3">{t('contextLoading')}</p> : null}
          {context.isError ? <Alert>{t('contextUnavailable')}</Alert> : null}
          {context.data ? (
            <>
              <p className="mt-3 text-sm text-slate-700">{context.data.document_title}</p>
              <p className="mt-3 whitespace-pre-wrap text-slate-800">{context.data.context}</p>
            </>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
