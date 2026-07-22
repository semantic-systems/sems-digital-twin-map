import { QueryClient } from '@tanstack/react-query';

/**
 * Single query client for the app. Fetch orchestration policy:
 *
 * - The reports/dots bundle is ONE query keyed on the full filter params
 *   (['bundle', params]). React Query then provides everything the app used
 *   to hand-roll: stale responses can't overwrite a newer key's data (the old
 *   loadSeqRef), overlapping refreshes are deduped (the old dots token guard),
 *   and switching filters keeps the previous list visible while loading
 *   (placeholderData: keepPreviousData).
 *
 * - The bundle has NO refetch interval. A tiny /reports/version change token
 *   is polled instead (see App.tsx); the bundle refetches only when the token
 *   moves — so the steady-state 10s poll costs one indexed-aggregate query,
 *   not the full facet pipeline.
 *
 * - Every user mutation (acknowledge / hide / flag / location edit / admit)
 *   calls invalidateBundle() after its PATCH resolves. Invalidation also
 *   CANCELS an in-flight bundle fetch and starts a fresh one, so a poll
 *   response computed before the mutation can never be applied over it —
 *   strictly stronger than the snapshot-comparison guards it replaces.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
    },
  },
});

export function invalidateBundle(): void {
  void queryClient.invalidateQueries({ queryKey: ['bundle'] });
}
