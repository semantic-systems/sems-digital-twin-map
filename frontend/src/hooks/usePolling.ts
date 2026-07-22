import { useEffect, useRef } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore, activeLocFilter } from '../store/useFilterStore';
import { useUserStore } from '../store/useUserStore';
import { admitAllReports, fetchReports } from '../api/reports';
import { refreshDots } from '../store/useReportStore';

const INTERVAL_MS = 10_000;

export function usePolling() {
  const { username } = useUserStore();
  const { setReports, setPendingNewCount, setUnseenCount, currentLimit, pendingNewCount } = useReportStore();
  const filters = useFilterStore();
  const { setAllPlatforms, setPlatformCounts, setPlatformAddedCounts } = filters;
  const timerRef = useRef<number | null>(null);
  // Guards against the scheduled tick and the "pending just appeared" effect below
  // both invoking pollRef.current() at once.
  const inFlightRef = useRef(false);

  // Keep a stable ref of the current poll function so the interval doesn't
  // need to be recreated every time a filter changes.
  const pollRef = useRef<() => Promise<void>>(async () => {});

  pollRef.current = async () => {
    if (!username) return;
    if (inFlightRef.current) return;
    inFlightRef.current = true;
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
        showOnlyNew: snapShowOnlyNew,
        showIssuesView: snapShowIssuesView,
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
        only_new: snapShowOnlyNew || undefined,
        only_issues: snapShowIssuesView || undefined,
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
        cur.locShowUnlocalized !== snapLocUnlocalized ||
        cur.showOnlyNew !== snapShowOnlyNew ||
        cur.showIssuesView !== snapShowIssuesView
      ) return;

      // Facet fields are null under lean views ("not computed, keep what you
      // had" — explicit in the API contract); the guards below skip null.
      if (reportsRes.all_platforms?.length) setAllPlatforms(reportsRes.all_platforms);
      if (reportsRes.platform_counts) setPlatformCounts(reportsRes.platform_counts);
      if (reportsRes.platform_added_counts) setPlatformAddedCounts(reportsRes.platform_added_counts);

      const pendingCount = reportsRes.pending_count ?? 0;

      if (snapAutoUpdate && pendingCount > 0) {
        await admitAllReports(username, {
          platforms: params.platforms,
          event_types: params.event_types,
          relevances: params.relevances,
          time_window: params.time_window,
          since: params.since,
          until: params.until,
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
          cur2.locShowUnlocalized !== snapLocUnlocalized ||
          cur2.showOnlyNew !== snapShowOnlyNew ||
          cur2.showIssuesView !== snapShowIssuesView
        ) return;
        // Null facets under lean views are preserved by setReports/the guards.
        setReports(
          reloaded.reports,
          reloaded.loaded_at,
          reloaded.event_type_totals ?? undefined,
          reloaded.relevance_totals ?? undefined,
          reloaded.has_more,
          reloaded.location_counts ?? undefined,
          reloaded.total_count,
          reloaded.unseen_count,
        );
        if (reloaded.all_platforms?.length) setAllPlatforms(reloaded.all_platforms);
        if (reloaded.platform_counts) setPlatformCounts(reloaded.platform_counts);
        if (reloaded.platform_added_counts) setPlatformAddedCounts(reloaded.platform_added_counts);
        await refreshDots(params);
        setPendingNewCount(0);
      } else {
        // Auto-update OFF: the admitted list only changes through the user's own
        // actions (acknowledge / hide / flag / admit), which already update the
        // store optimistically. Do NOT setReports here — a poll whose query ran
        // before an in-flight acknowledge committed would otherwise overwrite that
        // report back to new=true, making the unseen badge climb again. We still
        // refresh pending count and the metadata (platform/facet counts) above,
        // and re-sync the unseen badge to the authoritative server count (a single
        // number, safe to refresh — unlike the whole list — and it self-corrects
        // any drift from optimistic adjustments once acknowledges have persisted).
        setPendingNewCount(pendingCount);
        setUnseenCount(reportsRes.unseen_count ?? 0);
      }
    } catch {
      // swallow poll errors silently
    } finally {
      inFlightRef.current = false;
    }
  };

  const restartInterval = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      if (!document.hidden) pollRef.current();
    }, INTERVAL_MS);
  };

  useEffect(() => {
    if (!username) return;

    const handleVisibility = () => {
      if (!document.hidden) pollRef.current();
    };

    restartInterval();
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username]);

  // A load/reload (App.loadData, filter change, admit, ...) just revealed pending
  // reports while auto-update is on. Previously this sat waiting for the next
  // scheduled tick — up to INTERVAL_MS away regardless of how it lined up with
  // when the banner appeared — which is what made the "N new" banner visibly
  // linger for several seconds even though the browser was going to admit it
  // automatically anyway. Admit immediately instead, and restart the interval so
  // the next scheduled tick is a full INTERVAL_MS away again (not moments later).
  useEffect(() => {
    if (!username) return;
    if (!filters.autoUpdate) return;
    if (pendingNewCount <= 0) return;
    pollRef.current();
    restartInterval();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingNewCount, filters.autoUpdate, username]);
}
