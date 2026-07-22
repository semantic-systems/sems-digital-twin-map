import React, { useEffect, useRef } from 'react';
import { useUserStore } from './store/useUserStore';
import { useFilterStore, activeLocFilter } from './store/useFilterStore';
import { useReportStore, beginDotsRefresh, commitDotsIfCurrent } from './store/useReportStore';
import { fetchReportsBundle } from './api/reports';
import { fetchLayers } from './api/layers';
import { usePolling } from './hooks/usePolling';
import { UsernameModal } from './components/shared/UsernameModal';
import { FilterBar } from './components/filterbar/FilterBar';
import { Sidebar } from './components/sidebar/Sidebar';
import { MapView } from './components/map/MapView';
import { PickModeOverlay } from './components/map/PickModeOverlay';
import { HelpButton } from './components/shared/HelpModal';
import { maybeAutoStartTour } from './tour/tour';

const BASE_LIMIT = 200;

function AppInner(): React.ReactElement {
  const { username } = useUserStore();
  const { setAllPlatforms, setPlatformCounts, setPlatformAddedCounts, setProcessingStatusTotals, setReportsTotalCount, setReportsUnseenCount, setAvailableLayers, setActiveLayers, activeLayers, platforms, allPlatforms, eventTypes, relevances, showHidden, showFlagged, showUnflagged, search, timeWindow, customSince, customUntil, locShowLocalized, locShowPending, locShowUnlocalized, showOnlyNew, showIssuesView } =
    useFilterStore();
  const { setReports, setPendingNewCount, setIsLoading, reloadTrigger, currentLimit, setCurrentLimit } = useReportStore();

  usePolling();

  // Tracks the latest loadData call so stale concurrent responses are discarded.
  const loadSeqRef = useRef(0);

  const buildParams = (limit: number) => {
    return {
    username: username!,
    loc_filter: activeLocFilter({ locShowLocalized, locShowPending, locShowUnlocalized }),
    platforms: platforms.length ? platforms : allPlatforms,
    event_types: eventTypes,
    relevances,
    show_hidden: showHidden,
    show_flagged: showFlagged,
    show_unflagged: showUnflagged,
    search: search || undefined,
    time_window: timeWindow,
    since: timeWindow === 'custom' ? (customSince || undefined) : undefined,
    until: timeWindow === 'custom' ? (customUntil || undefined) : undefined,
    only_new: showOnlyNew || undefined,
    only_issues: showIssuesView || undefined,
    limit,
    };
  };

  const loadData = async (limit: number) => {
    if (!username) return;
    const seq = ++loadSeqRef.current;
    // Also claim the dots-refresh token at the START of this attempt (not after
    // it resolves) so it participates in the SAME shared ordering guard as the
    // standalone dots-only refreshes (location edits, auto-update poll) — see
    // useReportStore's beginDotsRefresh/commitDotsIfCurrent.
    const dotsToken = beginDotsRefresh();
    setIsLoading(true);
    try {
      const params = buildParams(limit);

      // Reports + dots in a single round trip (see fetchReportsBundle).
      const reportsRes = await fetchReportsBundle(params);

      // Discard if a newer loadData started while this one was in-flight.
      if (seq !== loadSeqRef.current) return;

      // Under "only new"/"issues" the backend skips the facet scan and returns empty
      // panel counts; keep the last-known ones by passing undefined (setReports
      // preserves them) and skipping the platform-count setters.
      const isLeanView = showOnlyNew || showIssuesView;
      setReports(
        reportsRes.reports,
        reportsRes.loaded_at,
        isLeanView ? undefined : reportsRes.event_type_totals,
        isLeanView ? undefined : reportsRes.relevance_totals,
        reportsRes.has_more,
        isLeanView ? undefined : reportsRes.location_counts,
        reportsRes.total_count,
        reportsRes.unseen_count,
      );
      commitDotsIfCurrent(reportsRes.dots, dotsToken);
      setPendingNewCount(reportsRes.pending_count ?? 0);
      // processing_status_totals (Issues-view total, via its sum) and
      // reports_total_count/reports_unseen_count (Reports-view totals) are always
      // computed server-side regardless of the active tab — see
      // report_service.get_reports — so both tab pills AND the combined header
      // (Sidebar.tsx) stay live no matter which tab is currently open.
      if (reportsRes.processing_status_totals) {
        setProcessingStatusTotals(reportsRes.processing_status_totals);
      }
      setReportsTotalCount(reportsRes.reports_total_count ?? 0);
      setReportsUnseenCount(reportsRes.reports_unseen_count ?? 0);

      if (!isLeanView) {
        if (reportsRes.all_platforms && reportsRes.all_platforms.length > 0) {
          setAllPlatforms(reportsRes.all_platforms);
        }
        if (reportsRes.platform_counts) {
          setPlatformCounts(reportsRes.platform_counts);
        }
        if (reportsRes.platform_added_counts) {
          setPlatformAddedCounts(reportsRes.platform_added_counts);
        }
      }
    } catch (e) {
      console.error('Failed to load reports:', e);
    } finally {
      // Only the newest request clears the flag; a stale one resolving late must
      // not turn off the indicator while the current reload is still running.
      if (seq === loadSeqRef.current) setIsLoading(false);
    }
  };

  const loadMore = () => {
    // Backend caps `limit` at 2000 (Query le=2000); never request beyond it.
    const newLimit = Math.min(currentLimit + BASE_LIMIT, 2000);
    if (newLimit === currentLimit) return;
    setCurrentLimit(newLimit);
    loadData(newLimit);
  };

  // Initial load — on mount and when filters/search change (always reset to base limit)
  useEffect(() => {
    if (!username) return;
    setCurrentLimit(BASE_LIMIT);
    loadData(BASE_LIMIT);
  }, [username, platforms, eventTypes, relevances, showHidden, showFlagged, showUnflagged, search, timeWindow, customSince, customUntil, locShowLocalized, locShowPending, locShowUnlocalized, showOnlyNew, showIssuesView, reloadTrigger]);

  // Load layers list once; auto-activate all layers if none are active yet (fresh deployment)
  useEffect(() => {
    fetchLayers()
      .then((res) => {
        if (res.layers.length > 0) {
          setAvailableLayers(res.layers);
          if (activeLayers.length === 0) {
            setActiveLayers(res.layers.map((l) => l.id));
          }
        }
      })
      .catch(() => {});
  }, []);

  // First-time onboarding: walk new users through the map, list, search and
  // filters once. Replayable anytime via "Take a tour" in the help modal.
  useEffect(() => {
    maybeAutoStartTour();
  }, []);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
      }}
    >
      <HelpButton />
      <FilterBar />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Sidebar onLoadMore={loadMore} />
        <div data-app-region="map" style={{ flex: 1, position: 'relative', minWidth: 0 }}>
          <MapView />
          <PickModeOverlay />
        </div>
      </div>
    </div>
  );
}

function App(): React.ReactElement {
  const { username } = useUserStore();

  if (!username) {
    return <UsernameModal />;
  }

  return <AppInner />;
}

export default App;
