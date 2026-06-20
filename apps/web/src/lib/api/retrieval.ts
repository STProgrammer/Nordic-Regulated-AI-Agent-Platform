import {
  apiRequest,
  retrievalSearchInputSchema,
  retrievalSourceSchema,
  type RetrievalSearchInput,
  type RetrievalSource,
} from '@/lib/api/contracts';

export const retrievalApi = {
  search(input: RetrievalSearchInput): Promise<RetrievalSource[]> {
    const payload = retrievalSearchInputSchema.parse(input);
    return apiRequest('/api/retrieval/search', retrievalSourceSchema.array(), {
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },
};
