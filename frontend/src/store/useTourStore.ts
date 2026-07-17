import { create } from 'zustand';

interface TourStore {
  /**
   * The tour's example report's real id, while a tour has it loaded — lets
   * other state derivations (e.g. useVisibleReports' showHidden filter) treat
   * it specially without the tour module reaching into their internals.
   */
  activeExampleReportId: number | null;
  setActiveExampleReportId: (id: number | null) => void;
  /**
   * True while the tour's "a dot on the map" step is showing. The tour invites
   * clicking the dot, and Leaflet's native popup opens regardless — but
   * selecting it (setActiveReportId) would restyle the marker (bigger, blue,
   * "!" gone), and react-leaflet swaps in a brand new icon DOM element for
   * that, invalidating Shepherd's cached reference to the one it's attached
   * to (the tooltip collapses to a 0,0 fallback position). Suppressing just
   * the selection side effect for this one step keeps the marker's own DOM
   * node stable; selecting it for real happens moments later anyway, on the
   * "example report" step.
   */
  dotStepActive: boolean;
  setDotStepActive: (v: boolean) => void;
}

export const useTourStore = create<TourStore>((set) => ({
  activeExampleReportId: null,
  setActiveExampleReportId: (id) => set({ activeExampleReportId: id }),
  dotStepActive: false,
  setDotStepActive: (v) => set({ dotStepActive: v }),
}));
