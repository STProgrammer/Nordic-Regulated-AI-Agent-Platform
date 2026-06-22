import {
  ApiFailure,
  apiRequest,
  approvalActionResultSchema,
  approvalCommentInputSchema,
  approvalQueueSchema,
  approvalReassignInputSchema,
  approvalReviewPacketSchema,
  approvedOutputFormatSchema,
  editAndApproveInputSchema,
  jsonRequest,
  mockHandoffInputSchema,
  mockHandoffResultSchema,
  type ApprovalActionResult,
  type ApprovalCommentInput,
  type ApprovalQueue,
  type ApprovalReassignInput,
  type ApprovalReviewPacket,
  type ApprovedOutputFormat,
  type EditAndApproveInput,
  type MockHandoffInput,
  type MockHandoffResult,
} from '@/lib/api/contracts';

function approvalPath(path = ''): string {
  return `/api/approvals${path}`;
}

function post<TInput>(path: string, payload: TInput, schema: typeof approvalActionResultSchema) {
  return apiRequest(path, schema, jsonRequest('POST', payload));
}

const exportMetadata = {
  json: { filename: 'approved-output.json', mediaType: 'application/json' },
  csv: { filename: 'approved-output.csv', mediaType: 'text/csv' },
  markdown: { filename: 'approved-output.md', mediaType: 'text/markdown' },
  pdf: { filename: 'approved-output.pdf', mediaType: 'application/pdf' },
} as const;

export type ApprovedOutputDownload = {
  content: Blob;
  filename: (typeof exportMetadata)[ApprovedOutputFormat]['filename'];
};

export const approvalsApi = {
  list(limit = 25, offset = 0): Promise<ApprovalQueue> {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return apiRequest(`${approvalPath()}?${query.toString()}`, approvalQueueSchema);
  },

  get(approvalId: string): Promise<ApprovalReviewPacket> {
    return apiRequest(
      approvalPath(`/${encodeURIComponent(approvalId)}`),
      approvalReviewPacketSchema,
    );
  },

  approve(approvalId: string, input: ApprovalCommentInput): Promise<ApprovalActionResult> {
    return post(
      approvalPath(`/${encodeURIComponent(approvalId)}/approve`),
      approvalCommentInputSchema.parse(input),
      approvalActionResultSchema,
    );
  },

  editAndApprove(approvalId: string, input: EditAndApproveInput): Promise<ApprovalActionResult> {
    return post(
      approvalPath(`/${encodeURIComponent(approvalId)}/edit-and-approve`),
      editAndApproveInputSchema.parse(input),
      approvalActionResultSchema,
    );
  },

  reject(approvalId: string, input: ApprovalCommentInput): Promise<ApprovalActionResult> {
    return post(
      approvalPath(`/${encodeURIComponent(approvalId)}/reject`),
      approvalCommentInputSchema.parse(input),
      approvalActionResultSchema,
    );
  },

  requestMoreEvidence(
    approvalId: string,
    input: ApprovalCommentInput,
  ): Promise<ApprovalActionResult> {
    return post(
      approvalPath(`/${encodeURIComponent(approvalId)}/request-more-evidence`),
      approvalCommentInputSchema.parse(input),
      approvalActionResultSchema,
    );
  },

  reassign(approvalId: string, input: ApprovalReassignInput): Promise<ApprovalActionResult> {
    return post(
      approvalPath(`/${encodeURIComponent(approvalId)}/reassign`),
      approvalReassignInputSchema.parse(input),
      approvalActionResultSchema,
    );
  },

  async exportApprovedOutput(
    approvalId: string,
    exportFormat: ApprovedOutputFormat,
  ): Promise<ApprovedOutputDownload> {
    const format = approvedOutputFormatSchema.parse(exportFormat);
    const expected = exportMetadata[format];
    let response: Response;
    try {
      response = await fetch(approvalPath(`/${encodeURIComponent(approvalId)}/exports/${format}`), {
        credentials: 'include',
        headers: { Accept: expected.mediaType },
        method: 'POST',
      });
    } catch {
      throw new ApiFailure({ code: 'network_error', status: 0 });
    }
    if (!response.ok) {
      throw new ApiFailure({ code: 'api_error', status: response.status });
    }
    if (
      !response.headers.get('content-type')?.startsWith(expected.mediaType) ||
      response.headers.get('content-disposition') !== `attachment; filename="${expected.filename}"`
    ) {
      throw new ApiFailure({ code: 'invalid_response', status: response.status });
    }
    const content = await response.blob();
    if (content.size === 0) {
      throw new ApiFailure({ code: 'invalid_response', status: response.status });
    }
    return { content, filename: expected.filename };
  },

  recordMockHandoff(approvalId: string, input: MockHandoffInput): Promise<MockHandoffResult> {
    return apiRequest(
      approvalPath(`/${encodeURIComponent(approvalId)}/mock-handoffs`),
      mockHandoffResultSchema,
      jsonRequest('POST', mockHandoffInputSchema.parse(input)),
    );
  },
};

export function saveApprovedOutput(download: ApprovedOutputDownload): void {
  const url = URL.createObjectURL(download.content);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = download.filename;
  anchor.style.display = 'none';
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
