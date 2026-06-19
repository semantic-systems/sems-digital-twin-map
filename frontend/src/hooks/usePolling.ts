import { useEffect, useRef } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore } from '../store/useFilterStore';
import { useUserStore } from '../store/useUserStore';
import { admitAllReports, fetchReports, fetchDots } from '../api/reports';

const INTERVAL_MS = 10_000;

export function usePolling() {
  const { username } = useUserStore();
  const { setReports, setDots, setPendingNewCount, currentLimit } = useReportStore();
  const filters = useFilterStore();
  const { setAllPlatforms, setPlatformCounts, setPlatformAddedCounts } = filters;
  const timerRef = useRef<number | null>(null);

  // Keep a stable ref of the current poll function so the interval doesn't
  // need to be recreated every time a filter changes.
  const pollRef = useRef<() => Promise<void>>(async () => {});

  pollRef.current = async () => {
    if (!username) return;
    try {
      // Snapshot filter identity before the async fetch. After awaiting, if any
      // filter has changed (loadData fired mid-flight), discard this response to
      // avoid briefly reverting the map/sidebar to stale data.
      const {
        platforms: snapPlatforms,
        allPlatforms: snapAllPlatforms,
        eventTypes: snapEvents,
        relevances: snapRelevances,
        showHidden: snapHidden,
        showFlagged: snapFlagged,
        showUnflagged: snapUnflagged,
        search: snapSearch,
        autoUpdate: snapAutoUpdate,
      } = filters;

      const params = {
        username,
        loc_filter: 'all',
        platforms: snapPlatforms.length ? snapPlatforms : snapAllPlatforms,
        event_types: snapEvents,
        relevances: snapRelevances,
        show_hidden: snapHidden,
        show_flagged: snapFlagged,
        show_unflagged: snapUnflagged,
        search: snapSearch || undefined,
        limit: currentLimit,
      };

      // Fetch reports to get pending_count AND up-to-date metadata (platform counts etc.)
      const reportsRes = await fetchReports(params);

      // Discard if filters changed while the request was in-flight.
      const cur = useFilterStore.getState();
      if (
        cur.platforms !== snapPlatforms ||
        cur.eventTypes !== snapEvents ||
        cur.relevances !== snapRelevances ||
        cur.showHidden !== snapHidden ||
        cur.showFlagged !== snapFlagged ||
        cur.showUnflagged !== snapUnflagged ||
        cur.search !== snapSearch
      ) return;

      if (reportsRes.all_platforms?.length) setAllPlatforms(reportsRes.all_platforms);
      if (reportsRes.platform_counts) setPlatformCounts(reportsRes.platform_counts);
      if (reportsRes.platform_added_counts) setPlatformAddedCounts(reportsRes.platform_added_counts);

      const pendingCount = reportsRes.pending_count ?? 0;

      if (snapAutoUpdate && pendingCount > 0) {
        await admitAllReports(username, {
          platforms: params.platforms,
          event_types: params.event_types,
          relevances: params.relevances,
        });
        const reloaded = await fetchReports(params);
        // Check again after the second await.
        const cur2 = useFilterStore.getState();
        if (
          cur2.platforms !== snapPlatforms ||
          cur2.eventTypes !== snapEvents ||
          cur2.relevances !== snapRelevances ||
          cur2.showHidden !== snapHidden ||
          cur2.showFlagged !== snapFlagged ||
          cur2.showUnflagged !== snapUnflagged ||
          cur2.search !== snapSearch
        ) return;
        setReports(reloaded.reports, reloaded.loaded_at, reloaded.event_type_totals, reloaded.relevance_totals, reloaded.has_more, reloaded.location_counts);
        if (reloaded.all_platforms?.length) setAllPlatforms(reloaded.all_platforms);
        if (reloaded.platform_counts) setPlatformCounts(reloaded.platform_counts);
        if (reloaded.platform_added_counts) setPlatformAddedCounts(reloaded.platform_added_counts);
        const dotsRes = await fetchDots(params);
        setDots(dotsRes.dots);
        setPendingNewCount(0);
      } else {
        setReports(reportsRes.reports, reportsRes.loaded_at, reportsRes.event_type_totals, reportsRes.relevance_totals, reportsRes.has_more, reportsRes.location_counts);
        setPendingNewCount(pendingCount);
      }
    } catch {
      // swallow poll errors silently
    }
  };

  useEffect(() => {
    if (!username) return;

    const handleVisibility = () => {
      if (!document.hidden) pollRef.current();
    };

    timerRef.current = window.setInterval(() => {
      if (!document.hidden) pollRef.current();
    }, INTERVAL_MS);

    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [username]);
}
