import { apiRequest, riskAssessmentSchema, type RiskAssessment } from '@/lib/api/contracts';

export const riskApi = {
  get(caseId: string): Promise<RiskAssessment> {
    return apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/risk-assessment`,
      riskAssessmentSchema,
    );
  },
};
