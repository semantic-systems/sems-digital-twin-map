import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { LayerDTO, DotsParams } from '../types';
import { LAYER_COLORS } from '../constants';

export const ALL_EVENT_TYPES_LIST = [
  'Menschen betroffen',
  'Warnungen & Hinweise',
  'Evakuierungen & Umsiedlungen',
  'Spenden & Freiwillige',
  'Infrastruktur-Schäden',
  'Verletzte & Tote',
  'Vermisste & Gefundene',
  'Bedarfe & Anfragen',
  'Einsatzmaßnahmen',
  'Mitgefühl & Unterstützung',
  'Sonstiges',
];

export const ALL_RELEVANCES_LIST = ['high', 'medium', 'low', 'none'];

/** Build the `loc_filter` query param from the location-type toggles.
 *  Returns undefined when all three are on (no restriction) — matching the
 *  backend contract where a full set means "no filter". */
export function activeLocFilter(f: {
  locShowLocalized: boolean;
  locShowPending: boolean;
  locShowUnlocalized: boolean;
}): string[] | undefined {
  const active = [
    ...(f.locShowLocalized ? ['localized'] : []),
    ...(f.locShowPending ? ['pending'] : []),
    ...(f.locShowUnlocalized ? ['unlocalized'] : []),
  ];
  return active.length < 3 ? active : undefined;
}

/** Full DotsParams from the current filter state — the single source of truth for
 *  dot refetches so location-edit refreshes (pin-set, map-drag, restore) carry the
 *  SAME filters as the main load. Omitting any of these here makes filtered-out dots
 *  reappear after an edit. */
export function dotsParamsFromFilters(
  f: {
    platforms: string[];
    allPlatforms: string[];
    eventTypes: string[];
    relevances: string[];
    showHidden: boolean;
    showFlagged: boolean;
    showUnflagged: boolean;
    search: string;
    timeWindow: string;
    customSince: string | null;
    customUntil: string | null;
    showOnlyNew: boolean;
    // Optional so pre-Issues-tab callers/tests that build this shape by hand
    // (e.g. useFilterStore.test.ts fixtures) remain valid; undefined = false.
    showIssuesView?: boolean;
    locShowLocalized: boolean;
    locShowPending: boolean;
    locShowUnlocalized: boolean;
    // The drawn-area filter — sent to the backend (which applies it via PostGIS),
    // so it's part of the request/query key and a redraw triggers a refetch.
    // Optional for pre-existing callers/tests that build this shape by hand.
    spatialPolygon?: [number, number][] | null;
  },
): DotsParams {
  return {
    loc_filter: activeLocFilter(f),
    platforms: f.platforms.length ? f.platforms : f.allPlatforms,
    event_types: f.eventTypes,
    relevances: f.relevances,
    show_hidden: f.showHidden,
    show_flagged: f.showFlagged,
    show_unflagged: f.showUnflagged,
    search: f.search || undefined,
    time_window: f.timeWindow,
    since: f.timeWindow === 'custom' ? (f.customSince || undefined) : undefined,
    until: f.timeWindow === 'custom' ? (f.customUntil || undefined) : undefined,
    only_new: f.showOnlyNew || undefined,
    only_issues: f.showIssuesView || undefined,
    area: encodeArea(f.spatialPolygon),
  };
}

/** Encode a drawn-area ring as a flat 'lat,lon,lat,lon,…' string (5-dp rounded) for
 *  the `area` query param; undefined when no area is drawn. */
export function encodeArea(ring: [number, number][] | null | undefined): string | undefined {
  if (!ring || ring.length < 3) return undefined;
  return ring.flatMap(([lat, lon]) => [lat.toFixed(5), lon.toFixed(5)]).join(',');
}

/** Derive a stable color for a layer based on its position in availableLayers. */
export function getLayerColor(layerId: number, availableLayers: LayerDTO[]): string {
  const idx = availableLayers.findIndex((l) => l.id === layerId);
  if (idx < 0) return '#6366f1';
  return LAYER_COLORS[idx % LAYER_COLORS.length];
}

interface FilterStore {
  locShowLocalized: boolean;
  locShowPending: boolean;
  locShowUnlocalized: boolean;
  relevances: string[];
  platforms: string[];
  allPlatforms: string[];
  platformCounts: Record<string, number>;
  platformAddedCounts: Record<string, number>;
  // Extraction-issue counts by status ('error'/'no_text'), for the Issues tab badge.
  // Always computed server-side regardless of which tab is active — see App.loadData.
  processingStatusTotals: Record<string, number>;
  // Reports-view totals — the Reports-view counterpart to processingStatusTotals'
  // sum, also always computed server-side regardless of which tab is active, so
  // both pills and the combined header stay informative on whichever tab is open.
  reportsTotalCount: number;
  reportsUnseenCount: number;
  showHidden: boolean;
  showFlagged: boolean;
  showUnflagged: boolean;
  eventTypes: string[];
  activeLayers: number[];
  availableLayers: LayerDTO[];
  autoUpdate: boolean;
  search: string;
  timeWindow: string;
  // Custom time range (ISO strings) — active when timeWindow === 'custom'
  customSince: string | null;
  customUntil: string | null;
  // Spatial area filter — [lat, lon][] polygon drawn on the map
  spatialPolygon: [number, number][] | null;
  spatialDrawMode: boolean;
  // Client-side view filter: show only reports still marked new (unacknowledged).
  showOnlyNew: boolean;
  // "Issues" tab: show only reports whose extraction pipeline failed, instead of
  // the normal reports view. Mutually exclusive with showOnlyNew in the UI.
  showIssuesView: boolean;

  setLocShowLocalized: (v: boolean) => void;
  setLocShowPending: (v: boolean) => void;
  setLocShowUnlocalized: (v: boolean) => void;
  setRelevances: (v: string[]) => void;
  setPlatforms: (v: string[]) => void;
  setAllPlatforms: (v: string[]) => void;
  setPlatformCounts: (v: Record<string, number>) => void;
  setPlatformAddedCounts: (v: Record<string, number>) => void;
  setProcessingStatusTotals: (v: Record<string, number>) => void;
  setReportsTotalCount: (v: number) => void;
  setReportsUnseenCount: (v: number) => void;
  setShowHidden: (v: boolean) => void;
  setShowFlagged: (v: boolean) => void;
  setShowUnflagged: (v: boolean) => void;
  toggleEventType: (type: string) => void;
  soloEventType: (type: string) => void;
  setActiveLayers: (ids: number[]) => void;
  toggleLayer: (id: number) => void;
  setAvailableLayers: (layers: LayerDTO[]) => void;
  setAutoUpdate: (v: boolean) => void;
  setSearch: (v: string) => void;
  setTimeWindow: (v: string) => void;
  setCustomRange: (since: string | null, until: string | null) => void;
  setSpatialPolygon: (p: [number, number][] | null) => void;
  setSpatialDrawMode: (v: boolean) => void;
  setShowOnlyNew: (v: boolean) => void;
  setShowIssuesView: (v: boolean) => void;
}

export const useFilterStore = create<FilterStore>()(
  persist(
    (set, get) => ({
      locShowLocalized: true,
      locShowPending: true,
      locShowUnlocalized: true,
      relevances: [...ALL_RELEVANCES_LIST],
      platforms: [],
      allPlatforms: [],
      platformCounts: {},
      platformAddedCounts: {},
      processingStatusTotals: {},
      reportsTotalCount: 0,
      reportsUnseenCount: 0,
      showHidden: false,
      showFlagged: true,
      showUnflagged: true,
      eventTypes: [...ALL_EVENT_TYPES_LIST],
      activeLayers: [],
      availableLayers: [],
      // Recommended default — new reports merge in automatically rather than
      // sitting behind the "N new posts" bar. Only affects users with no
      // persisted filter state yet (see the persist() config below); anyone
      // who already toggled this explicitly keeps their own choice.
      autoUpdate: true,
      search: '',
      timeWindow: 'all',
      customSince: null,
      customUntil: null,
      spatialPolygon: null,
      spatialDrawMode: false,
      showOnlyNew: false,
      showIssuesView: false,

      setLocShowLocalized: (locShowLocalized) => set({ locShowLocalized }),
      setLocShowPending: (locShowPending) => set({ locShowPending }),
      setLocShowUnlocalized: (locShowUnlocalized) => set({ locShowUnlocalized }),
      setRelevances: (relevances) => set({ relevances }),
      setPlatforms: (platforms) => set({ platforms }),
      setAllPlatforms: (allPlatforms) => set({ allPlatforms }),
      setPlatformCounts: (platformCounts) => set({ platformCounts }),
      setPlatformAddedCounts: (platformAddedCounts) => set({ platformAddedCounts }),
      setProcessingStatusTotals: (processingStatusTotals) => set({ processingStatusTotals }),
      setReportsTotalCount: (reportsTotalCount) => set({ reportsTotalCount }),
      setReportsUnseenCount: (reportsUnseenCount) => set({ reportsUnseenCount }),
      setShowHidden: (showHidden) => set({ showHidden }),
      setShowFlagged: (showFlagged) => set({ showFlagged }),
      setShowUnflagged: (showUnflagged) => set({ showUnflagged }),
      toggleEventType: (type) => {
        const cur = get().eventTypes;
        set({
          eventTypes: cur.includes(type)
            ? cur.filter((e) => e !== type)
            : [...cur, type],
        });
      },
      soloEventType: (type) =>
        set((s) => ({
          eventTypes:
            s.eventTypes.length === 1 && s.eventTypes[0] === type
              ? [...ALL_EVENT_TYPES_LIST]
              : [type],
        })),
      setActiveLayers: (ids) => set({ activeLayers: ids }),
      setAvailableLayers: (availableLayers) => set({ availableLayers }),
      toggleLayer: (id) => {
        const cur = get().activeLayers;
        set({
          activeLayers: cur.includes(id)
            ? cur.filter((l) => l !== id)
            : [...cur, id],
        });
      },
      setAutoUpdate: (autoUpdate) => set({ autoUpdate }),
      setSearch: (search) => set({ search }),
      // Selecting a preset window clears any active custom range.
      setTimeWindow: (timeWindow) => set({ timeWindow, customSince: null, customUntil: null }),
      setCustomRange: (customSince, customUntil) =>
        set({ timeWindow: 'custom', customSince, customUntil }),
      setSpatialPolygon: (spatialPolygon) => set({ spatialPolygon, spatialDrawMode: false }),
      setSpatialDrawMode: (spatialDrawMode) => set({ spatialDrawMode }),
      // The two tabs are mutually exclusive — turning one on always turns the other off.
      setShowOnlyNew: (showOnlyNew) => set({ showOnlyNew, showIssuesView: showOnlyNew ? false : get().showIssuesView }),
      setShowIssuesView: (showIssuesView) => set({ showIssuesView, showOnlyNew: showIssuesView ? false : get().showOnlyNew }),
    }),
    {
      name: 'sems-filters-v2',
      // Don't persist draw mode or the "only new"/"issues" view filters — always
      // start idle (a persisted one could reopen into a confusingly empty list).
      partialize: (s) => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { spatialDrawMode, showOnlyNew, showIssuesView, ...rest } = s;
        return rest;
      },
    },
  ),
);
