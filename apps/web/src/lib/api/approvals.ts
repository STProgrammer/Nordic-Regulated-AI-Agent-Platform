import {
  apiRequest,
  approvalActionResultSchema,
  approvalCommentInputSchema,
  approvalQueueSchema,
  approvalReassignInputSchema,
  approvalReviewPacketSchema,
  editAndApproveInputSchema,
  type ApprovalActionResult,
  type ApprovalCommentInput,
  type ApprovalQueue,
  type ApprovalReassignInput,
  type ApprovalReviewPacket,
  type EditAndApproveInput,
} from '@/lib/api/contracts';

function approvalPath(path = ''): string {
  return `/api/approvals${path}`;
}

function post<TInput>(path: string, payload: TInput, schema: typeof approvalActionResultSchema) {
  return apiRequest(path, schema, {
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  });
}

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
};
