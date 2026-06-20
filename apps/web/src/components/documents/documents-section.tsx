'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { documentsApi } from '@/lib/api/documents';
import {
  ApiFailure,
  documentSourceStatusSchema,
  type DocumentData,
  type DocumentSourceStatus,
} from '@/lib/api/contracts';
import { useCurrentUser } from '@/lib/auth/query';
import { documentQueryKeys, useDocumentDetail, useDocumentList } from '@/lib/documents/query';
import { formatFileSize, formatTimestamp } from '@/lib/formatting';

const governanceRoles = new Set(['Admin', 'Compliance Reviewer']);
const reindexRoles = new Set(['Admin', 'Case Worker', 'Manager']);

export function DocumentsSection({ caseId }: { caseId: string }) {
  const t = useTranslations('documents');
  const documents = useDocumentList(caseId);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  return (
    <section
      aria-labelledby="documents-title"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-semibold" id="documents-title">
          {t('title')}
        </h2>
        <p className="text-sm text-slate-600">{t('metadataOnly')}</p>
      </div>
      {documents.isPending ? (
        <p className="mt-4" role="status">
          {t('loading')}
        </p>
      ) : null}
      {documents.isError ? (
        <Alert>
          <p>{t('unavailable')}</p>
          <Button className="mt-3" onClick={() => void documents.refetch()}>
            {t('retry')}
          </Button>
        </Alert>
      ) : null}
      {documents.data?.items.length === 0 ? (
        <p className="mt-4 text-slate-700">{t('empty')}</p>
      ) : null}
      {documents.data?.items.length ? (
        <ul className="mt-4 space-y-3" aria-label={t('listLabel')}>
          {documents.data.items.map((document) => (
            <li className="rounded-lg border border-slate-200 p-4" key={document.document_id}>
              <DocumentListItem
                document={document}
                onInspect={() => setSelectedDocumentId(document.document_id)}
              />
            </li>
          ))}
        </ul>
      ) : null}
      {documents.data?.has_more ? (
        <p className="mt-4 text-sm text-slate-600">{t('moreAvailable')}</p>
      ) : null}
      {selectedDocumentId ? (
        <DocumentDetail
          documentId={selectedDocumentId}
          onClose={() => setSelectedDocumentId(null)}
        />
      ) : null}
    </section>
  );
}

function DocumentListItem({
  document,
  onInspect,
}: {
  document: DocumentData;
  onInspect: () => void;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('documents');
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h3 className="font-semibold">{document.title}</h3>
        <p className="mt-1 text-sm text-slate-700">
          {document.original_filename} · {document.file_type.toUpperCase()} ·{' '}
          {formatFileSize(document.file_size_bytes, locale)}
        </p>
        <p className="mt-2 text-sm text-slate-700">
          {t('sourceStatusLabel')}: {t(`sourceStatuses.${document.source_status}`)} ·{' '}
          {t('confidentialityLabel')}: {t(`confidentiality.${document.confidentiality_level}`)}
        </p>
      </div>
      <Button
        className="bg-white text-slate-900 ring-1 ring-slate-300 hover:bg-slate-100"
        onClick={onInspect}
      >
        {t('inspect')}
      </Button>
    </div>
  );
}

function DocumentDetail({ documentId, onClose }: { documentId: string; onClose: () => void }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('documents');
  const detail = useDocumentDetail(documentId);
  if (detail.isPending)
    return (
      <p className="mt-4" role="status">
        {t('detailLoading')}
      </p>
    );
  if (detail.isError || !detail.data) {
    return (
      <Alert>
        <p>{t('detailUnavailable')}</p>
        <Button className="mt-3" onClick={onClose}>
          {t('close')}
        </Button>
      </Alert>
    );
  }
  const document = detail.data;
  return (
    <section
      aria-labelledby="document-detail-title"
      className="mt-5 rounded-lg border border-sky-200 bg-sky-50 p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold" id="document-detail-title">
            {t('detailTitle')}
          </h3>
          <p className="mt-1 text-sm text-slate-700">{document.title}</p>
        </div>
        <Button
          className="bg-white text-slate-900 ring-1 ring-slate-300 hover:bg-slate-100"
          onClick={onClose}
        >
          {t('close')}
        </Button>
      </div>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <Definition
          label={t('fileLabel')}
          value={`${document.original_filename} (${document.file_type.toUpperCase()})`}
        />
        <Definition
          label={t('sizeLabel')}
          value={formatFileSize(document.file_size_bytes, locale)}
        />
        <Definition label={t('languageLabel')} value={document.language ?? t('unknown')} />
        <Definition
          label={t('pagesLabel')}
          value={document.page_count === null ? t('unknown') : String(document.page_count)}
        />
        <Definition label={t('parsingLabel')} value={t(`parsing.${document.parsing_status}`)} />
        <Definition label={t('indexingLabel')} value={t(`indexing.${document.indexing_status}`)} />
        <Definition
          label={t('sourceStatusLabel')}
          value={t(`sourceStatuses.${document.source_status}`)}
        />
        <Definition
          label={t('confidentialityLabel')}
          value={t(`confidentiality.${document.confidentiality_level}`)}
        />
        <Definition
          label={t('updatedLabel')}
          value={formatTimestamp(document.updated_at, locale)}
        />
      </dl>
      {document.parsing_error ? (
        <Alert>
          <p>{t('parsingError')}</p>
        </Alert>
      ) : null}
      {document.indexing_error ? (
        <Alert>
          <p>{t('indexingError')}</p>
        </Alert>
      ) : null}
      <DocumentActions document={document} />
    </section>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-medium text-slate-700">{label}</dt>
      <dd className="mt-1">{value}</dd>
    </div>
  );
}

function DocumentActions({ document }: { document: DocumentData }) {
  const t = useTranslations('documents');
  const currentUser = useCurrentUser();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<DocumentSourceStatus>(document.source_status);
  const isGovernanceUser =
    currentUser.data?.roles.some((role) => governanceRoles.has(role)) ?? false;
  const canReindex = currentUser.data?.roles.some((role) => reindexRoles.has(role)) ?? false;
  const reindexReady =
    document.parsing_status === 'parsed' &&
    !['pending', 'indexing'].includes(document.indexing_status);
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: documentQueryKeys.all });
    await queryClient.invalidateQueries({
      queryKey: documentQueryKeys.detail(document.document_id),
    });
  };
  const updateStatus = useMutation({
    mutationFn: () => documentsApi.updateSourceStatus(document.document_id, status),
    onSuccess: invalidate,
  });
  const reindex = useMutation({
    mutationFn: () => documentsApi.reindex(document.document_id),
    onSuccess: invalidate,
  });
  const mutationError = updateStatus.error ?? reindex.error;
  return (
    <div className="mt-5 space-y-4 border-t border-sky-200 pt-4">
      {isGovernanceUser ? (
        <div>
          <label
            className="block font-medium"
            htmlFor={`document-source-status-${document.document_id}`}
          >
            {t('changeSourceStatus')}
          </label>
          <p className="mt-1 text-sm text-slate-700">{t('archivedHelp')}</p>
          <div className="mt-2 flex flex-wrap gap-3">
            <select
              className="rounded-md border border-slate-400 bg-white px-3 py-2"
              id={`document-source-status-${document.document_id}`}
              onChange={(event) => setStatus(event.target.value as DocumentSourceStatus)}
              value={status}
            >
              {documentSourceStatusSchema.options.map((option) => (
                <option key={option} value={option}>
                  {t(`sourceStatuses.${option}`)}
                </option>
              ))}
            </select>
            <Button
              disabled={updateStatus.isPending || status === document.source_status}
              onClick={() => void updateStatus.mutateAsync()}
            >
              {updateStatus.isPending ? t('saving') : t('saveStatus')}
            </Button>
          </div>
        </div>
      ) : null}
      {canReindex ? (
        <div>
          <Button
            disabled={!reindexReady || reindex.isPending}
            onClick={() => void reindex.mutateAsync()}
          >
            {reindex.isPending ? t('reindexing') : t('reindex')}
          </Button>
          {!reindexReady ? (
            <p className="mt-2 text-sm text-slate-700">{t('reindexUnavailable')}</p>
          ) : null}
        </div>
      ) : null}
      {mutationError ? (
        <Alert>
          <p>
            {mutationError instanceof ApiFailure && mutationError.status === 409
              ? t('actionConflict')
              : t('actionFailed')}
          </p>
        </Alert>
      ) : null}
      {updateStatus.isSuccess ? (
        <p aria-live="polite" className="text-sm text-emerald-800">
          {t('statusSaved')}
        </p>
      ) : null}
      {reindex.isSuccess ? (
        <p aria-live="polite" className="text-sm text-emerald-800">
          {t('reindexRequested')}
        </p>
      ) : null}
    </div>
  );
}
