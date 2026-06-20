import type { QueryClient } from '@tanstack/react-query';
import { useQuery } from '@tanstack/react-query';

import { authApi } from '@/lib/api/auth';
import { ApiFailure, type CurrentUser } from '@/lib/api/contracts';

export const authQueryKey = ['auth', 'current-user'] as const;

export function shouldRetryAuthQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiFailure && [401, 403, 422, 429, 503].includes(error.status)) {
    return false;
  }

  return failureCount < 1;
}

export function useCurrentUser() {
  return useQuery<CurrentUser, ApiFailure>({
    queryFn: authApi.getCurrentUser,
    queryKey: authQueryKey,
    retry: shouldRetryAuthQuery,
  });
}

export async function refreshCurrentUser(queryClient: QueryClient): Promise<CurrentUser> {
  await queryClient.invalidateQueries({ queryKey: authQueryKey });
  return queryClient.fetchQuery({
    queryFn: authApi.getCurrentUser,
    queryKey: authQueryKey,
    staleTime: 0,
  });
}
