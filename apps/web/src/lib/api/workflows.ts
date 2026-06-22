'use client';

import {
  apiRequest,
  evidenceStartInputSchema,
  draftingStartInputSchema,
  extractionStartInputSchema,
  intakeCorrectionInputSchema,
  intakeStartInputSchema,
  jsonRequest,
  riskComplianceStartInputSchema,
  workflowTraceSchema,
  workflowRunSchema,
  type IntakeCorrectionInput,
  type WorkflowTrace,
  type WorkflowRun,
} from '@/lib/api/contracts';

function runPath(runId: string): string {
  return `/api/workflows/${encodeURIComponent(runId)}`;
}

export const workflowsApi = {
  startIntake(caseId: string): Promise<WorkflowRun> {
    return apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/workflows/run`,
      workflowRunSchema,
      jsonRequest('POST', intakeStartInputSchema.parse({ workflow: 'intake' })),
    );
  },

  startEvidence(caseId: string): Promise<WorkflowRun> {
    return apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/workflows/run`,
      workflowRunSchema,
      jsonRequest('POST', evidenceStartInputSchema.parse({ workflow: 'evidence' })),
    );
  },

  startExtraction(caseId: string): Promise<WorkflowRun> {
    return apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/workflows/run`,
      workflowRunSchema,
      jsonRequest('POST', extractionStartInputSchema.parse({ workflow: 'extraction' })),
    );
  },

  startDrafting(caseId: string, outputLanguage?: 'nb' | 'en'): Promise<WorkflowRun> {
    return apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/workflows/run`,
      workflowRunSchema,
      jsonRequest(
        'POST',
        draftingStartInputSchema.parse({
          workflow: 'drafting',
          ...(outputLanguage ? { output_language: outputLanguage } : {}),
        }),
      ),
    );
  },

  startRiskCompliance(caseId: string): Promise<WorkflowRun> {
    return apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/workflows/run`,
      workflowRunSchema,
      jsonRequest('POST', riskComplianceStartInputSchema.parse({ workflow: 'risk_compliance' })),
    );
  },

  get(runId: string): Promise<WorkflowRun> {
    return apiRequest(runPath(runId), workflowRunSchema);
  },

  getTrace(runId: string): Promise<WorkflowTrace> {
    return apiRequest(`${runPath(runId)}/trace`, workflowTraceSchema);
  },

  correct(runId: string, input: IntakeCorrectionInput): Promise<WorkflowRun> {
    const payload = intakeCorrectionInputSchema.parse(input);
    return apiRequest(
      `${runPath(runId)}/intake/correction`,
      workflowRunSchema,
      jsonRequest('POST', payload),
    );
  },
};
