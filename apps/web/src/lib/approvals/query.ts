import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { approvalsApi } from '@/lib/api/approvals';
import {
  ApiFailure,
  type ApprovalCommentInput,
  type ApprovalReassignInput,
  type EditAndApproveInput,
  type MockHandoffInput,
} from '@/lib/api/contracts';
import { caseQueryKeys } from '@/lib/cases/query';

export const approvalQueryKeys = {
  all: ['approvals'] as const,
  detail: (approvalId: string) => [...approvalQueryKeys.all, 'detail', approvalId] as const,
  queue: () => [...approvalQueryKeys.all, 'queue'] as const,
};

function shouldRetryApprovalQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiFailure && [400, 401, 403, 404, 409, 422].includes(error.status)) {
    return false;
  }
  return failureCount < 1;
}

export function useApprovalQueue() {
  return useQuery({
    queryFn: () => approvalsApi.list(),
    queryKey: approvalQueryKeys.queue(),
    retry: shouldRetryApprovalQuery,
  });
}

export function useApprovalPacket(approvalId: string, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => approvalsApi.get(approvalId),
    queryKey: approvalQueryKeys.detail(approvalId),
    refetchInterval: (query) =>
      query.state.data?.workflow_status === 'waiting_for_human_review' ||
      query.state.data?.workflow_status === 'running'
        ? 1500
        : false,
    retry: shouldRetryApprovalQuery,
  });
}

export function useApprovalActions(approvalId: string) {
  const queryClient = useQueryClient();
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: approvalQueryKeys.all }),
      queryClient.invalidateQueries({ queryKey: caseQueryKeys.all }),
    ]);
  };
  return {
    approve: useMutation({
      mutationFn: (input: ApprovalCommentInput) => approvalsApi.approve(approvalId, input),
      onSuccess: refresh,
    }),
    editAndApprove: useMutation({
      mutationFn: (input: EditAndApproveInput) => approvalsApi.editAndApprove(approvalId, input),
      onSuccess: refresh,
    }),
    reject: useMutation({
      mutationFn: (input: ApprovalCommentInput) => approvalsApi.reject(approvalId, input),
      onSuccess: refresh,
    }),
    requestMoreEvidence: useMutation({
      mutationFn: (input: ApprovalCommentInput) =>
        approvalsApi.requestMoreEvidence(approvalId, input),
      onSuccess: refresh,
    }),
    reassign: useMutation({
      mutationFn: (input: ApprovalReassignInput) => approvalsApi.reassign(approvalId, input),
      onSuccess: refresh,
    }),
    mockHandoff: useMutation({
      mutationFn: (input: MockHandoffInput) => approvalsApi.recordMockHandoff(approvalId, input),
      onSuccess: refresh,
    }),
  };
}
