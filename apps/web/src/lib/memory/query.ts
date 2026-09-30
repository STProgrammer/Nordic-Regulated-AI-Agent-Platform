import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { memoryApi } from '@/lib/api/memory';
import { ApiFailure, type ControlledMemoryInput } from '@/lib/api/contracts';

export const memoryQueryKeys = {
  all: ['controlled-memory'] as const,
  entries: () => [...memoryQueryKeys.all, 'entries'] as const,
  settings: () => [...memoryQueryKeys.all, 'settings'] as const,
};

function shouldRetryMemoryQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiFailure && [400, 401, 403, 404, 409, 422, 503].includes(error.status)) {
    return false;
  }
  return failureCount < 1;
}

export function useControlledMemory(enabled: boolean) {
  return {
    entries: useQuery({
      enabled,
      queryFn: () => memoryApi.listEntries(),
      queryKey: memoryQueryKeys.entries(),
      retry: shouldRetryMemoryQuery,
    }),
    settings: useQuery({
      enabled,
      queryFn: memoryApi.getSettings,
      queryKey: memoryQueryKeys.settings(),
      retry: shouldRetryMemoryQuery,
    }),
  };
}

export function useControlledMemoryActions() {
  const queryClient = useQueryClient();
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: memoryQueryKeys.all });
  };
  return {
    archive: useMutation({
      mutationFn: memoryApi.archiveEntry,
      onSuccess: refresh,
    }),
    add: useMutation({
      mutationFn: (input: ControlledMemoryInput) => memoryApi.addEntry(input),
      onSuccess: refresh,
    }),
    revise: useMutation({
      mutationFn: ({ entryId, input }: { entryId: string; input: ControlledMemoryInput }) =>
        memoryApi.reviseEntry(entryId, input),
      onSuccess: refresh,
    }),
    settings: useMutation({
      mutationFn: memoryApi.updateSettings,
      onSuccess: refresh,
    }),
  };
}
