import React, { useEffect, useRef } from 'react';
import { useUserStore } from './store/useUserStore';
import { useFilterStore, activeLocFilter } from './store/useFilterStore';
import { useReportStore } from './store/useReportStore';
import { fetchReportsBundle } from './api/reports';
import { fetchLayers } from './api/layers';
import { usePolling } from './hooks/usePolling';
import { UsernameModal } from './components/shared/UsernameModal';
import { FilterBar } from './components/filterbar/FilterBar';
import { Sidebar } from './components/sidebar/Sidebar';
import { MapView } from './components/map/MapView';
import { PickModeOverlay } from './components/map/PickModeOverlay';

const BASE_LIMIT = 50;

function AppInner(): React.ReactElement {
  const { username } = useUserStore();
  const { setAllPlatforms, setPlatformCounts, setPlatformAddedCounts, setAvailableLayers, setActiveLayers, activeLayers, platforms, allPlatforms, eventTypes, relevances, showHidden, showFlagged, showUnflagged, search, timeWindow, customSince, customUntil, locShowLocalized, locShowPending, locShowUnlocalized } =
    useFilterStore();
  const { setReports, setDots, setPendingNewCount, reloadTrigger, currentLimit, setCurrentLimit } = useReportStore();

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
    limit,
    };
  };

  const loadData = async (limit: number) => {
    if (!username) return;
    const seq = ++loadSeqRef.current;
    try {
      const params = buildParams(limit);

      // Reports + dots in a single round trip (see fetchReportsBundle).
      const reportsRes = await fetchReportsBundle(params);

      // Discard if a newer loadData started while this one was in-flight.
      if (seq !== loadSeqRef.current) return;

      setReports(reportsRes.reports, reportsRes.loaded_at, reportsRes.event_type_totals, reportsRes.relevance_totals, reportsRes.has_more, reportsRes.location_counts, reportsRes.total_count);
      setDots(reportsRes.dots);
      setPendingNewCount(reportsRes.pending_count ?? 0);

      if (reportsRes.all_platforms && reportsRes.all_platforms.length > 0) {
        setAllPlatforms(reportsRes.all_platforms);
      }
      if (reportsRes.platform_counts) {
        setPlatformCounts(reportsRes.platform_counts);
      }
      if (reportsRes.platform_added_counts) {
        setPlatformAddedCounts(reportsRes.platform_added_counts);
      }
    } catch (e) {
      console.error('Failed to load reports:', e);
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
  }, [username, platforms, eventTypes, relevances, showHidden, showFlagged, showUnflagged, search, timeWindow, customSince, customUntil, locShowLocalized, locShowPending, locShowUnlocalized, reloadTrigger]);

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
      <FilterBar />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Sidebar onLoadMore={loadMore} />
        <div style={{ flex: 1, position: 'relative', minWidth: 0 }}>
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
