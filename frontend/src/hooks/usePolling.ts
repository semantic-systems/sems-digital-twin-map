import { useEffect, useRef } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore } from '../store/useFilterStore';
import { useUserStore } from '../store/useUserStore';
import { admitAllReports, fetchReports, fetchDots } from '../api/reports';

const INTERVAL_MS = 10_000;

export function usePolling() {
  const { username } = useUserStore();
  const { setReports, setDots, setPendingNewCount } = useReportStore();
  const filters = useFilterStore();
  const { setAllPlatforms, setPlatformCounts, setPlatformAddedCounts } = filters;
  const timerRef = useRef<number | null>(null);

  // Keep a stable ref of the current poll function so the interval doesn't
  // need to be recreated every time a filter changes.
  const pollRef = useRef<() => Promise<void>>(async () => {});

  pollRef.current = async () => {
    if (!username) return;
    try {
      const params = {
        username,
        loc_filter: filters.locFilter,
        platforms: filters.platforms.length ? filters.platforms : filters.allPlatforms,
        event_types: filters.eventTypes,
        relevances: filters.relevances,
        show_hidden: filters.showHidden,
        show_flagged: filters.showFlagged,
        show_unflagged: filters.showUnflagged,
      };

      // Fetch reports to get pending_count AND up-to-date metadata (platform counts etc.)
      const reportsRes = await fetchReports(params);
      if (reportsRes.all_platforms?.length) setAllPlatforms(reportsRes.all_platforms);
      if (reportsRes.platform_counts) setPlatformCounts(reportsRes.platform_counts);
      if (reportsRes.platform_added_counts) setPlatformAddedCounts(reportsRes.platform_added_counts);

      const pendingCount = reportsRes.pending_count ?? 0;

      if (filters.autoUpdate && pendingCount > 0) {
        await admitAllReports(username, {
          platforms: params.platforms,
          event_types: params.event_types,
          relevances: params.relevances,
        });
        const reloaded = await fetchReports(params);
        setReports(reloaded.reports, reloaded.loaded_at, reloaded.event_type_totals);
        if (reloaded.all_platforms?.length) setAllPlatforms(reloaded.all_platforms);
        if (reloaded.platform_counts) setPlatformCounts(reloaded.platform_counts);
        if (reloaded.platform_added_counts) setPlatformAddedCounts(reloaded.platform_added_counts);
        const dotsRes = await fetchDots(params);
        setDots(dotsRes.dots);
        setPendingNewCount(0);
      } else {
        setReports(reportsRes.reports, reportsRes.loaded_at, reportsRes.event_type_totals);
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
