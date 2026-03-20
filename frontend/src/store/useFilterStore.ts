import { create } from 'zustand';
import { persist } from 'zustand/middleware';

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

interface FilterStore {
  locFilter: 'all' | 'localized' | 'pending' | 'unlocalized';
  relevances: string[];
  platforms: string[];
  allPlatforms: string[];
  platformCounts: Record<string, number>;
  showHidden: boolean;
  showFlagged: boolean;
  showUnflagged: boolean;
  eventTypes: string[];
  activeLayers: number[];
  autoUpdate: boolean;

  setLocFilter: (v: FilterStore['locFilter']) => void;
  setRelevances: (v: string[]) => void;
  setPlatforms: (v: string[]) => void;
  setAllPlatforms: (v: string[]) => void;
  setPlatformCounts: (v: Record<string, number>) => void;
  setShowHidden: (v: boolean) => void;
  setShowFlagged: (v: boolean) => void;
  setShowUnflagged: (v: boolean) => void;
  toggleEventType: (type: string) => void;
  soloEventType: (type: string) => void;
  setActiveLayers: (ids: number[]) => void;
  toggleLayer: (id: number) => void;
  setAutoUpdate: (v: boolean) => void;
}

export const useFilterStore = create<FilterStore>()(
  persist(
    (set, get) => ({
      locFilter: 'all',
      relevances: [...ALL_RELEVANCES_LIST],
      platforms: [],
      allPlatforms: [],
      platformCounts: {},
      showHidden: false,
      showFlagged: true,
      showUnflagged: true,
      eventTypes: ALL_EVENT_TYPES_LIST.filter((e) => e !== 'Irrelevant'),
      activeLayers: [],
      autoUpdate: false,

      setLocFilter: (locFilter) => set({ locFilter }),
      setRelevances: (relevances) => set({ relevances }),
      setPlatforms: (platforms) => set({ platforms }),
      setAllPlatforms: (allPlatforms) => set({ allPlatforms }),
      setPlatformCounts: (platformCounts) => set({ platformCounts }),
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
      toggleLayer: (id) => {
        const cur = get().activeLayers;
        set({
          activeLayers: cur.includes(id)
            ? cur.filter((l) => l !== id)
            : [...cur, id],
        });
      },
      setAutoUpdate: (autoUpdate) => set({ autoUpdate }),
    }),
    { name: 'sems-filters-v2' },
  ),
);
