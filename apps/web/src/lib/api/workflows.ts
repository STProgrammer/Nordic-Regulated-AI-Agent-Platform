'use client';

import {
  apiRequest,
  evidenceStartInputSchema,
  intakeCorrectionInputSchema,
  intakeStartInputSchema,
  workflowRunSchema,
  type IntakeCorrectionInput,
  type WorkflowRun,
} from '@/lib/api/contracts';

function runPath(runId: string): string {
  return `/api/workflows/${encodeURIComponent(runId)}`;
}

export const workflowsApi = {
  startIntake(caseId: string): Promise<WorkflowRun> {
    return apiRequest(`/api/cases/${encodeURIComponent(caseId)}/workflows/run`, workflowRunSchema, {
      body: JSON.stringify(intakeStartInputSchema.parse({ workflow: 'intake' })),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },

  startEvidence(caseId: string): Promise<WorkflowRun> {
    return apiRequest(`/api/cases/${encodeURIComponent(caseId)}/workflows/run`, workflowRunSchema, {
      body: JSON.stringify(evidenceStartInputSchema.parse({ workflow: 'evidence' })),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },

  get(runId: string): Promise<WorkflowRun> {
    return apiRequest(runPath(runId), workflowRunSchema);
  },

  correct(runId: string, input: IntakeCorrectionInput): Promise<WorkflowRun> {
    const payload = intakeCorrectionInputSchema.parse(input);
    return apiRequest(`${runPath(runId)}/intake/correction`, workflowRunSchema, {
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },
};
