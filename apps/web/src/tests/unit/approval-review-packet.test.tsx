import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApprovalReviewPacket } from '@/components/approval/approval-review-packet';
import { approvalsApi, saveApprovedOutput } from '@/lib/api/approvals';
import { authApi } from '@/lib/api/auth';
import type {
  ApprovalReviewPacket as ApprovalReviewPacketData,
  CurrentUser,
} from '@/lib/api/contracts';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({ authApi: { getCurrentUser: vi.fn() } }));
vi.mock('@/lib/api/documents', () => ({ documentsApi: { getContext: vi.fn() } }));
vi.mock('@/lib/api/approvals', () => ({
  approvalsApi: {
    approve: vi.fn(),
    editAndApprove: vi.fn(),
    exportApprovedOutput: vi.fn(),
    get: vi.fn(),
    list: vi.fn(),
    recordMockHandoff: vi.fn(),
    reassign: vi.fn(),
    reject: vi.fn(),
    requestMoreEvidence: vi.fn(),
  },
  saveApprovedOutput: vi.fn(),
}));

const approvalId = '33333333-3333-4333-8333-333333333333';
const user: CurrentUser = {
  display_name: 'Synthetic reviewer',
  organization_id: '11111111-1111-4111-8111-111111111111',
  preferred_language: 'nb',
  roles: ['Compliance Reviewer'],
  user_id: '22222222-2222-4222-8222-222222222222',
};
const packet: ApprovalReviewPacketData = {
  ai_draft: 'Synthetic immutable AI draft.',
  approval_id: approvalId,
  approval_status: 'approved',
  assigned_user_id: user.user_id,
  case_id: '44444444-4444-4444-8444-444444444444',
  case_number: 'CASE-28',
  case_status: 'approved',
  case_title: 'Synthetic approved case',
  decision: 'edit_and_approve',
  decision_at: '2030-01-01T00:00:00Z',
  extracted_fields: [],
  final_text: 'Synthetic final human-approved output.',
  reviewer_comment: null,
  reviewer_user_id: user.user_id,
  risk_level: 'high',
  risk_reasons: [],
  sources: [],
  workflow_status: 'completed',
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(authApi.getCurrentUser).mockResolvedValue(user);
  vi.mocked(approvalsApi.get).mockResolvedValue(packet);
  vi.mocked(approvalsApi.exportApprovedOutput).mockResolvedValue({
    content: new Blob(['synthetic']),
    filename: 'approved-output.pdf',
  });
  vi.mocked(approvalsApi.recordMockHandoff).mockResolvedValue({
    approval_id: approvalId,
    mode: 'mock',
    status: 'recorded',
    target: 'teams',
  });
});

describe('Approval review packet approved-output actions', () => {
  it('shows fixed downloads only after terminal approval and confirms mock handoffs', async () => {
    const actor = userEvent.setup();
    renderWithProviders(<ApprovalReviewPacket approvalId={approvalId} />);

    expect(await screen.findByTestId('approved-output-actions')).toBeInTheDocument();
    await actor.click(screen.getByTestId('approved-output-download-pdf'));
    expect(approvalsApi.exportApprovedOutput).toHaveBeenCalledWith(approvalId, 'pdf');
    expect(saveApprovedOutput).toHaveBeenCalledWith(
      expect.objectContaining({ filename: 'approved-output.pdf' }),
    );

    await actor.click(screen.getByTestId('mock-handoff-teams'));
    expect(screen.getByTestId('mock-handoff-confirmation')).toBeInTheDocument();
    await actor.click(screen.getByTestId('mock-handoff-confirm'));
    expect(approvalsApi.recordMockHandoff).toHaveBeenCalledWith(approvalId, { target: 'teams' });
    expect(
      await screen.findByText('Den simulerte overleveringen er registrert.'),
    ).toBeInTheDocument();
  });
});
