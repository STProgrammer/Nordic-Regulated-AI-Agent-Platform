import {
  apiRequest,
  jsonRequest,
  retrievalSearchInputSchema,
  retrievalSourceSchema,
  type RetrievalSearchInput,
  type RetrievalSource,
} from '@/lib/api/contracts';

export const retrievalApi = {
  search(input: RetrievalSearchInput): Promise<RetrievalSource[]> {
    const payload = retrievalSearchInputSchema.parse(input);
    return apiRequest(
      '/api/retrieval/search',
      retrievalSourceSchema.array(),
      jsonRequest('POST', payload),
    );
  },
};
