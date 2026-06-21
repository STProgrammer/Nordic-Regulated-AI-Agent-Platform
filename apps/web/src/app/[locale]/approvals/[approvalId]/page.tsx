import { ApprovalReviewPacket } from '@/components/approval/approval-review-packet';

export default async function ApprovalPacketPage({
  params,
}: {
  params: Promise<{ approvalId: string }>;
}) {
  const { approvalId } = await params;
  return <ApprovalReviewPacket approvalId={approvalId} />;
}
