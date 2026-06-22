'use client';

import {
  apiRequest,
  extractedFieldEditInputSchema,
  extractedFieldListSchema,
  extractedFieldSchema,
  jsonRequest,
  type ExtractedField,
  type ExtractedFieldEditInput,
} from '@/lib/api/contracts';

function fieldsPath(caseId: string): string {
  return `/api/cases/${encodeURIComponent(caseId)}/extraction/fields`;
}

export const extractionApi = {
  list(caseId: string): Promise<ExtractedField[]> {
    return apiRequest(fieldsPath(caseId), extractedFieldListSchema).then((data) => data.items);
  },

  edit(caseId: string, fieldId: string, input: ExtractedFieldEditInput): Promise<ExtractedField> {
    return apiRequest(
      `${fieldsPath(caseId)}/${encodeURIComponent(fieldId)}`,
      extractedFieldSchema,
      jsonRequest('PATCH', extractedFieldEditInputSchema.parse(input)),
    );
  },
};
