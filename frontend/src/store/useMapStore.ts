import { create } from 'zustand';

interface PickMode {
  reportId: number;
  locIndex: number | null;
  mention: string | null;
}

interface MapStore {
  pickMode: PickMode | null;
  fitBoundsRequest: [[number, number], [number, number]] | null;
  enterPickMode: (reportId: number, locIndex?: number | null, mention?: string | null) => void;
  exitPickMode: () => void;
  requestFitBounds: (bounds: [[number, number], [number, number]]) => void;
  clearFitBounds: () => void;
}

export const useMapStore = create<MapStore>((set) => ({
  pickMode: null,
  fitBoundsRequest: null,

  enterPickMode: (reportId, locIndex = null, mention = null) =>
    set({ pickMode: { reportId, locIndex, mention } }),

  exitPickMode: () => set({ pickMode: null }),

  requestFitBounds: (bounds) => set({ fitBoundsRequest: bounds }),

  clearFitBounds: () => set({ fitBoundsRequest: null }),
}));
