import { create } from 'zustand';
import type { ReportDTO, DotDTO, LocationEntry } from '../types';

interface ReportStore {
  reports: ReportDTO[];
  dots: DotDTO[];
  activeReportId: number | null;
  pendingNewCount: number;
  loadedAt: string | null;
  eventTypeTotals: Record<string, number>;
  reloadTrigger: number;

  setReports: (reports: ReportDTO[], loadedAt: string, eventTypeTotals?: Record<string, number>) => void;
  bumpReloadTrigger: () => void;
  setDots: (dots: DotDTO[]) => void;
  setActiveReportId: (id: number | null) => void;
  setPendingNewCount: (n: number) => void;

  // optimistic updates
  optimisticHide: (id: number, hide: boolean) => void;
  optimisticFlag: (author: string, flag: boolean) => void;
  optimisticAcknowledge: (id: number) => void;
  optimisticUpdateLocations: (id: number, locations: LocationEntry[]) => void;
  optimisticRestoreLocations: (id: number, originalLocations: LocationEntry[]) => void;
}

export const useReportStore = create<ReportStore>((set) => ({
  reports: [],
  dots: [],
  activeReportId: null,
  pendingNewCount: 0,
  loadedAt: null,
  eventTypeTotals: {},
  reloadTrigger: 0,

  setReports: (reports, loadedAt, eventTypeTotals = {}) => set({ reports, loadedAt, eventTypeTotals }),
  bumpReloadTrigger: () => set((s) => ({ reloadTrigger: s.reloadTrigger + 1 })),
  setDots: (dots) => set({ dots }),
  setActiveReportId: (id) => set({ activeReportId: id }),
  setPendingNewCount: (n) => set({ pendingNewCount: n }),

  optimisticHide: (id, hide) =>
    set((s) => ({
      reports: s.reports.map((r) =>
        r.id === id ? { ...r, user_state: { ...r.user_state, hide } } : r,
      ),
    })),

  optimisticFlag: (author, flag) =>
    set((s) => ({
      reports: s.reports.map((r) =>
        r.author === author
          ? {
              ...r,
              user_state: {
                ...r.user_state,
                flag,
                flag_author: flag ? author : null,
              },
            }
          : r,
      ),
    })),

  optimisticAcknowledge: (id) =>
    set((s) => ({
      reports: s.reports.map((r) =>
        r.id === id ? { ...r, user_state: { ...r.user_state, new: false } } : r,
      ),
      dots: s.dots.map((d) =>
        d.report_id === id ? { ...d, new: false } : d,
      ),
    })),

  optimisticUpdateLocations: (id, locations) =>
    set((s) => ({
      reports: s.reports.map((r) =>
        r.id === id
          ? { ...r, locations, user_state: { ...r.user_state, locations } }
          : r,
      ),
    })),

  optimisticRestoreLocations: (id, originalLocations) =>
    set((s) => ({
      reports: s.reports.map((r) =>
        r.id === id
          ? {
              ...r,
              locations: originalLocations,
              user_state: { ...r.user_state, locations: null },
            }
          : r,
      ),
    })),
}));
