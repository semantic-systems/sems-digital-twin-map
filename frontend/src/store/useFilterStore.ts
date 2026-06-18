import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { LayerDTO } from '../types';
import { LAYER_COLORS } from '../constants';

export const ALL_EVENT_TYPES_LIST = [
  'Irrelevant',
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
  // Spatial area filter — [lat, lon][] polygon drawn on the map
  spatialPolygon: [number, number][] | null;
  spatialDrawMode: boolean;

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
  setSpatialPolygon: (p: [number, number][] | null) => void;
  setSpatialDrawMode: (v: boolean) => void;
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
      eventTypes: ALL_EVENT_TYPES_LIST.filter((e) => e !== 'Irrelevant'),
      activeLayers: [],
      availableLayers: [],
      autoUpdate: false,
      search: '',
      spatialPolygon: null,
      spatialDrawMode: false,

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
              ? ALL_EVENT_TYPES_LIST.filter((e) => e !== 'Irrelevant')
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
      setSpatialPolygon: (spatialPolygon) => set({ spatialPolygon, spatialDrawMode: false }),
      setSpatialDrawMode: (spatialDrawMode) => set({ spatialDrawMode }),
    }),
    {
      name: 'sems-filters-v2',
      // Don't persist draw mode — always start idle
      partialize: (s) => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { spatialDrawMode, ...rest } = s;
        return rest;
      },
    },
  ),
);
