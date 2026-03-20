import React, { useEffect } from 'react';
import { useUserStore } from './store/useUserStore';
import { useFilterStore } from './store/useFilterStore';
import { useReportStore } from './store/useReportStore';
import { fetchReports, fetchDots } from './api/reports';
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
  const { setAllPlatforms, setPlatformCounts, setPlatformAddedCounts, setAvailableLayers, locFilter, platforms, allPlatforms, eventTypes, relevances, showHidden, showFlagged, showUnflagged, search } =
    useFilterStore();
  const { setReports, setDots, setPendingNewCount, reloadTrigger, currentLimit, setCurrentLimit } = useReportStore();

  usePolling();

  const buildParams = (limit: number) => ({
    username: username!,
    loc_filter: locFilter,
    platforms: platforms.length ? platforms : allPlatforms,
    event_types: eventTypes,
    relevances,
    show_hidden: showHidden,
    show_flagged: showFlagged,
    show_unflagged: showUnflagged,
    search: search || undefined,
    limit,
  });

  const loadData = async (limit: number) => {
    if (!username) return;
    try {
      const params = buildParams(limit);

      // Fetch reports and dots in parallel
      const [reportsRes, dotsRes] = await Promise.all([
        fetchReports(params),
        fetchDots(params),
      ]);

      setReports(reportsRes.reports, reportsRes.loaded_at, reportsRes.event_type_totals, reportsRes.relevance_totals, reportsRes.has_more);
      setDots(dotsRes.dots);
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
    const newLimit = currentLimit + BASE_LIMIT;
    setCurrentLimit(newLimit);
    loadData(newLimit);
  };

  // Initial load — on mount and when filters/search change (always reset to base limit)
  useEffect(() => {
    if (!username) return;
    setCurrentLimit(BASE_LIMIT);
    loadData(BASE_LIMIT);
  }, [username, locFilter, platforms, eventTypes, relevances, showHidden, showFlagged, showUnflagged, search, reloadTrigger]);

  // Load layers list once
  useEffect(() => {
    fetchLayers()
      .then((res) => { if (res.layers.length > 0) setAvailableLayers(res.layers); })
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
