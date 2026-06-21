import { EvaluationRunDetail } from '@/components/evaluation/evaluation-run-detail';

export default async function EvaluationRunPage({
  params,
}: {
  params: Promise<{ evaluationRunId: string }>;
}) {
  const { evaluationRunId } = await params;
  return <EvaluationRunDetail evaluationRunId={evaluationRunId} />;
}
