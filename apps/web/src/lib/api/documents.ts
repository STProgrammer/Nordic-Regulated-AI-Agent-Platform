import {
  apiRequest,
  documentDataSchema,
  documentListSchema,
  documentSourceContextSchema,
  documentSourceStatusSchema,
  jsonRequest,
  type DocumentData,
  type DocumentList,
  type DocumentSourceContext,
  type DocumentSourceStatus,
} from '@/lib/api/contracts';

function documentPath(path = ''): string {
  return `/api/documents${path}`;
}

export const documentsApi = {
  get(documentId: string): Promise<DocumentData> {
    return apiRequest(documentPath(`/${encodeURIComponent(documentId)}`), documentDataSchema);
  },

  getContext(documentId: string, chunkId: string): Promise<DocumentSourceContext> {
    const query = new URLSearchParams({ chunk_id: chunkId });
    return apiRequest(
      documentPath(`/${encodeURIComponent(documentId)}/context?${query.toString()}`),
      documentSourceContextSchema,
    );
  },

  list({
    caseId,
    limit = 25,
    offset = 0,
  }: {
    caseId: string;
    limit?: number;
    offset?: number;
  }): Promise<DocumentList> {
    const query = new URLSearchParams({
      case_id: caseId,
      limit: String(limit),
      offset: String(offset),
    });
    return apiRequest(`${documentPath()}?${query.toString()}`, documentListSchema);
  },

  reindex(documentId: string): Promise<DocumentData> {
    return apiRequest(
      documentPath(`/${encodeURIComponent(documentId)}/reindex`),
      documentDataSchema,
      {
        method: 'POST',
      },
    );
  },

  updateSourceStatus(
    documentId: string,
    sourceStatus: DocumentSourceStatus,
  ): Promise<DocumentData> {
    const payload = documentSourceStatusSchema.parse(sourceStatus);
    return apiRequest(
      documentPath(`/${encodeURIComponent(documentId)}/source-status`),
      documentDataSchema,
      jsonRequest('PATCH', { source_status: payload }),
    );
  },
};
