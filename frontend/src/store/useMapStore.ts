import { create } from 'zustand';

interface PickMode {
  reportId: number;
  locIndex: number | null;
  mention: string | null;
}

interface MapStore {
  pickMode: PickMode | null;
  fitBoundsRequest: [[number, number], [number, number]] | null;
  // A counter, not a boolean — bumping it is itself the signal (mirrors
  // fitBoundsRequest's request/response shape), so two closes in a row still
  // both fire even if nothing else about the state changed in between.
  closePopupRequest: number;
  enterPickMode: (reportId: number, locIndex?: number | null, mention?: string | null) => void;
  exitPickMode: () => void;
  requestFitBounds: (bounds: [[number, number], [number, number]]) => void;
  clearFitBounds: () => void;
  requestClosePopup: () => void;
}

export const useMapStore = create<MapStore>((set) => ({
  pickMode: null,
  fitBoundsRequest: null,
  closePopupRequest: 0,

  enterPickMode: (reportId, locIndex = null, mention = null) =>
    set({ pickMode: { reportId, locIndex, mention } }),

  exitPickMode: () => set({ pickMode: null }),

  requestFitBounds: (bounds) => set({ fitBoundsRequest: bounds }),

  clearFitBounds: () => set({ fitBoundsRequest: null }),

  requestClosePopup: () => set((s) => ({ closePopupRequest: s.closePopupRequest + 1 })),
}));
