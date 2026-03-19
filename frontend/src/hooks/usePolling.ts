import { useEffect, useRef } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore } from '../store/useFilterStore';
import { useUserStore } from '../store/useUserStore';
import { fetchNewCount, admitAllReports, fetchReports, fetchDots } from '../api/reports';

const INTERVAL_MS = 10_000;

export function usePolling() {
  const { username } = useUserStore();
  const { loadedAt, setReports, setDots, setPendingNewCount } = useReportStore();
  const filters = useFilterStore();
  const { setAllPlatforms } = filters;
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

      // Use epoch as "since" so we count ALL unadmitted reports, not just ones
      // newer than the last fetch. This keeps the banner in sync with pending_count
      // from fetchReports and prevents the banner from resetting to 0 on each poll.
      // Count ALL unadmitted reports regardless of event_type filter —
      // the banner is a notification mechanism, not a view filter.
      const { count } = await fetchNewCount({
        ...params,
        event_types: [],
        since: new Date(0).toISOString(),
      });

      if (count === 0) {
        setPendingNewCount(0);
        return;
      }

      if (filters.autoUpdate) {
        await admitAllReports(username);
        const reloaded = await fetchReports(params);
        setReports(reloaded.reports, reloaded.loaded_at, reloaded.event_type_totals);
        if (reloaded.all_platforms?.length) setAllPlatforms(reloaded.all_platforms);
        const dotsRes = await fetchDots(params);
        setDots(dotsRes.dots);
        setPendingNewCount(0);
      } else {
        setPendingNewCount(count);
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
