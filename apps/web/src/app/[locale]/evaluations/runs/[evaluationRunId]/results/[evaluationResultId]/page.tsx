import { EvaluationResultDetail } from '@/components/evaluation/evaluation-result-detail';

export default async function EvaluationResultPage({
  params,
}: {
  params: Promise<{ evaluationResultId: string; evaluationRunId: string }>;
}) {
  const { evaluationResultId, evaluationRunId } = await params;
  return (
    <EvaluationResultDetail
      evaluationResultId={evaluationResultId}
      evaluationRunId={evaluationRunId}
    />
  );
}
