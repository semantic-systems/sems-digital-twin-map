import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useUserStore } from './store/useUserStore';
import { useFilterStore, dotsParamsFromFilters } from './store/useFilterStore';
import { useReportStore } from './store/useReportStore';
import { fetchReportsBundle, fetchVersion, admitAllReports } from './api/reports';
import { fetchLayers } from './api/layers';
import { fetchMe } from './api/auth';
import { setUnauthorizedHandler } from './api/client';
import { queryClient, invalidateBundle } from './queryClient';
import { LoginPage } from './components/shared/LoginPage';
import { FilterBar } from './components/filterbar/FilterBar';
import { Sidebar } from './components/sidebar/Sidebar';
import { MapView } from './components/map/MapView';
import { PickModeOverlay } from './components/map/PickModeOverlay';
import { HelpButton } from './components/shared/HelpModal';
import { maybeAutoStartTour } from './tour/tour';

const BASE_LIMIT = 200;
const VERSION_POLL_MS = 10_000;
// Returning to a recently-viewed filter combination reuses the cached bundle;
// anything older than this refetches (also covers time-window aging on
// window-focus refetches, which a pure change-token poll can't see).
const BUNDLE_STALE_MS = 30_000;

function AppInner(): React.ReactElement {
  const { username } = useUserStore();
  const filterState = useFilterStore();
  const { setAllPlatforms, setPlatformCounts, setPlatformAddedCounts, setProcessingStatusTotals, setReportsTotalCount, setReportsUnseenCount, setAvailableLayers, setActiveLayers, activeLayers, autoUpdate } = filterState;
  const { setReports, setDots, setPendingNewCount, setIsLoading, reloadTrigger, currentLimit, setCurrentLimit } = useReportStore();

  // dotsParamsFromFilters is the single source of truth for turning filter
  // state into request params (also used by tests). filterKey (a stable string,
  // unlike filterState which gets a new object identity on every store change
  // whether relevant or not) drives the "reset to page 1" effect below without
  // an infinite loop — it deliberately excludes limit.
  const paramsBase = useMemo(
    () => dotsParamsFromFilters(filterState),
    [filterState],
  );
  const filterKey = JSON.stringify(paramsBase);
  // params doubles as the bundle query key, which is what makes stale-response
  // handling automatic: data is only ever delivered for the key it was fetched under.
  const params = useMemo(
    () => ({ ...paramsBase, limit: currentLimit }),
    [paramsBase, currentLimit],
  );

  // Reports + dots in a single round trip. No refetch interval here — the
  // version poll below invalidates this query when something actually changed,
  // and every user mutation calls invalidateBundle() (see queryClient.ts).
  const bundleQuery = useQuery({
    queryKey: ['bundle', params],
    queryFn: () => fetchReportsBundle(params),
    enabled: !!username,
    placeholderData: keepPreviousData,
    staleTime: BUNDLE_STALE_MS,
  });

  // Push fresh bundle data into the zustand stores all components read from.
  // Facet fields are null under the lean views ("not computed, keep what you
  // had" — explicit in the API contract); setReports preserves on nullish and
  // the platform setters are guarded the same way.
  useEffect(() => {
    const res = bundleQuery.data;
    if (!res) return;
    setReports(
      res.reports,
      res.loaded_at,
      res.event_type_totals ?? undefined,
      res.relevance_totals ?? undefined,
      res.has_more,
      res.location_counts ?? undefined,
      res.total_count,
      res.unseen_count,
    );
    setDots(res.dots);
    setPendingNewCount(res.pending_count ?? 0);
    // processing_status_totals (Issues-view total, via its sum) and
    // reports_total_count/reports_unseen_count (Reports-view totals) are always
    // computed server-side regardless of the active tab, so both tab pills AND
    // the combined header (Sidebar.tsx) stay live on whichever tab is open.
    if (res.processing_status_totals) {
      setProcessingStatusTotals(res.processing_status_totals);
    }
    setReportsTotalCount(res.reports_total_count ?? 0);
    setReportsUnseenCount(res.reports_unseen_count ?? 0);
    if (res.all_platforms && res.all_platforms.length > 0) {
      setAllPlatforms(res.all_platforms);
    }
    if (res.platform_counts) {
      setPlatformCounts(res.platform_counts);
    }
    if (res.platform_added_counts) {
      setPlatformAddedCounts(res.platform_added_counts);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bundleQuery.data]);

  // Loading indicator: first-ever load, or a filter change still showing the
  // previous key's data (isPlaceholderData). Background refetches of the SAME
  // key (version-poll invalidations) don't flash the spinner.
  useEffect(() => {
    setIsLoading(bundleQuery.isPending || bundleQuery.isPlaceholderData);
  }, [bundleQuery.isPending, bundleQuery.isPlaceholderData, setIsLoading]);

  // Cheap 10s change-token poll — the bundle only refetches when the token
  // moves, so an idle app costs one indexed-aggregate query per tick instead
  // of the full facet pipeline. Window-focus refetch is React Query's default,
  // so returning to the tab checks immediately.
  const versionQuery = useQuery({
    queryKey: ['version', username],
    queryFn: () => fetchVersion(),
    enabled: !!username,
    refetchInterval: VERSION_POLL_MS,
  });
  const lastTokenRef = useRef<string | null>(null);
  useEffect(() => {
    const token = versionQuery.data?.token;
    if (token == null) return;
    if (lastTokenRef.current !== null && token !== lastTokenRef.current) {
      invalidateBundle();
    }
    lastTokenRef.current = token;
  }, [versionQuery.data]);

  // Auto-admission: the moment a bundle reveals pending reports while
  // auto-update is on, advance the watermark and refetch — no "wait for the
  // next tick" gap, and the in-flight guard keeps it single-flight.
  const admitInFlightRef = useRef(false);
  useEffect(() => {
    const pending = bundleQuery.data?.pending_count ?? 0;
    if (!username || !autoUpdate || pending <= 0 || admitInFlightRef.current) return;
    admitInFlightRef.current = true;
    admitAllReports()
      .then(() => invalidateBundle())
      .catch((e) => console.error('Auto-admission failed:', e))
      .finally(() => {
        admitInFlightRef.current = false;
      });
  }, [bundleQuery.data, autoUpdate, username]);

  // Manual reload requests (demo reset etc.) still arrive via reloadTrigger.
  useEffect(() => {
    if (reloadTrigger > 0) invalidateBundle();
  }, [reloadTrigger]);

  // Filter/search changes reset pagination to the first page. Deliberately NOT
  // depending on currentLimit itself (filterKey excludes it) — that would loop.
  useEffect(() => {
    setCurrentLimit(BASE_LIMIT);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  const loadMore = () => {
    // Backend caps `limit` at 2000 (Query le=2000); never request beyond it.
    const newLimit = Math.min(currentLimit + BASE_LIMIT, 2000);
    if (newLimit === currentLimit) return;
    setCurrentLimit(newLimit);
  };

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
  const { username, authChecked, setAuth, setAuthChecked } = useUserStore();
  // Set when a 401 arrives on an already-authenticated session. Without it the
  // user is dropped on a blank login form with no clue what happened — which is
  // exactly how a browser silently refusing to store the session cookie looked
  // like "login does nothing" instead of a reportable error.
  const [sessionLost, setSessionLost] = useState(false);

  // On mount: probe the session (/auth/me) to decide login page vs app, and
  // register the global 401 handler so an expired session anywhere drops back to
  // the login screen and clears cached data.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuth(null);
      setSessionLost(true);
      queryClient.clear();
    });
    fetchMe()
      .then((me) => setAuth(me))
      .catch(() => setAuth(null))
      .finally(() => setAuthChecked(true));
  }, [setAuth, setAuthChecked]);

  if (!authChecked) {
    // Brief blank while the session probe resolves — avoids flashing the login
    // page for an already-authenticated user on every reload.
    return <div style={{ position: 'fixed', inset: 0, background: '#0f172a' }} />;
  }

  if (!username) {
    return (
      <LoginPage
        sessionLost={sessionLost}
        onLoggedIn={(me) => {
          setSessionLost(false);
          setAuth(me);
        }}
      />
    );
  }

  return <AppInner />;
}

export default App;
