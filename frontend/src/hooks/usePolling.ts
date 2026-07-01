import { useEffect, useRef } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore, activeLocFilter } from '../store/useFilterStore';
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
        timeWindow: snapTimeWindow,
        customSince: snapCustomSince,
        customUntil: snapCustomUntil,
        locShowLocalized: snapLocLocalized,
        locShowPending: snapLocPending,
        locShowUnlocalized: snapLocUnlocalized,
      } = filters;

      const params = {
        username,
        loc_filter: activeLocFilter({
          locShowLocalized: snapLocLocalized,
          locShowPending: snapLocPending,
          locShowUnlocalized: snapLocUnlocalized,
        }),
        platforms: snapPlatforms.length ? snapPlatforms : snapAllPlatforms,
        event_types: snapEvents,
        relevances: snapRelevances,
        show_hidden: snapHidden,
        show_flagged: snapFlagged,
        show_unflagged: snapUnflagged,
        search: snapSearch || undefined,
        time_window: snapTimeWindow,
        since: snapTimeWindow === 'custom' ? (snapCustomSince || undefined) : undefined,
        until: snapTimeWindow === 'custom' ? (snapCustomUntil || undefined) : undefined,
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
        cur.search !== snapSearch ||
        cur.timeWindow !== snapTimeWindow ||
        cur.customSince !== snapCustomSince ||
        cur.customUntil !== snapCustomUntil ||
        cur.locShowLocalized !== snapLocLocalized ||
        cur.locShowPending !== snapLocPending ||
        cur.locShowUnlocalized !== snapLocUnlocalized
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
          cur2.search !== snapSearch ||
          cur2.timeWindow !== snapTimeWindow ||
          cur2.customSince !== snapCustomSince ||
          cur2.customUntil !== snapCustomUntil ||
          cur2.locShowLocalized !== snapLocLocalized ||
          cur2.locShowPending !== snapLocPending ||
          cur2.locShowUnlocalized !== snapLocUnlocalized
        ) return;
        setReports(reloaded.reports, reloaded.loaded_at, reloaded.event_type_totals, reloaded.relevance_totals, reloaded.has_more, reloaded.location_counts, reloaded.total_count);
        if (reloaded.all_platforms?.length) setAllPlatforms(reloaded.all_platforms);
        if (reloaded.platform_counts) setPlatformCounts(reloaded.platform_counts);
        if (reloaded.platform_added_counts) setPlatformAddedCounts(reloaded.platform_added_counts);
        const dotsRes = await fetchDots(params);
        setDots(dotsRes.dots);
        setPendingNewCount(0);
      } else {
        // Auto-update OFF: the admitted list only changes through the user's own
        // actions (acknowledge / hide / flag / admit), which already update the
        // store optimistically. Do NOT setReports here — a poll whose query ran
        // before an in-flight acknowledge committed would otherwise overwrite that
        // report back to new=true, making the unseen badge climb again. We still
        // refresh pending count and the metadata (platform/facet counts) above.
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
