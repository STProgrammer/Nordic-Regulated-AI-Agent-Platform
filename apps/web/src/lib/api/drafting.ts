'use client';

import { apiRequest, draftSchema, type Draft } from '@/lib/api/contracts';

export const draftingApi = {
  get(caseId: string): Promise<Draft> {
    return apiRequest(`/api/cases/${encodeURIComponent(caseId)}/draft`, draftSchema);
  },
};
