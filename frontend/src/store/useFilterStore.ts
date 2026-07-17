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
  username: string,
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
    locShowLocalized: boolean;
    locShowPending: boolean;
    locShowUnlocalized: boolean;
  },
): DotsParams {
  return {
    username,
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
  };
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

  setLocShowLocalized: (v: boolean) => void;
  setLocShowPending: (v: boolean) => void;
  setLocShowUnlocalized: (v: boolean) => void;
  setRelevances: (v: string[]) => void;
  setPlatforms: (v: string[]) => void;
  setAllPlatforms: (v: string[]) => void;
  setPlatformCounts: (v: Record<string, number>) => void;
  setPlatformAddedCounts: (v: Record<string, number>) => void;
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

      setLocShowLocalized: (locShowLocalized) => set({ locShowLocalized }),
      setLocShowPending: (locShowPending) => set({ locShowPending }),
      setLocShowUnlocalized: (locShowUnlocalized) => set({ locShowUnlocalized }),
      setRelevances: (relevances) => set({ relevances }),
      setPlatforms: (platforms) => set({ platforms }),
      setAllPlatforms: (allPlatforms) => set({ allPlatforms }),
      setPlatformCounts: (platformCounts) => set({ platformCounts }),
      setPlatformAddedCounts: (platformAddedCounts) => set({ platformAddedCounts }),
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
      setShowOnlyNew: (showOnlyNew) => set({ showOnlyNew }),
    }),
    {
      name: 'sems-filters-v2',
      // Don't persist draw mode or the "only new" view filter — always start idle
      // (a persisted "only new" could reopen into a confusingly empty list).
      partialize: (s) => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { spatialDrawMode, showOnlyNew, ...rest } = s;
        return rest;
      },
    },
  ),
);
