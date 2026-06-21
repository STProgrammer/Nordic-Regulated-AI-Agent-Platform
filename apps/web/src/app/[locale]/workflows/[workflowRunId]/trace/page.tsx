import { WorkflowTrace } from '@/components/workflow/workflow-trace';

export default async function WorkflowTracePage({
  params,
}: {
  params: Promise<{ workflowRunId: string }>;
}) {
  const { workflowRunId } = await params;
  return <WorkflowTrace workflowRunId={workflowRunId} />;
}
