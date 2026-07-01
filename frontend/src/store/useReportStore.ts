import { create } from 'zustand';
import type { ReportDTO, DotDTO, LocationEntry } from '../types';

// A report contributes to the unseen badge when it is still new and not hidden.
// Used to keep unseenCount responsive to optimistic acknowledge/hide actions
// between server syncs.
const contributesToUnseen = (r: ReportDTO): boolean =>
  r.user_state.new && !r.user_state.hide;

interface ReportStore {
  reports: ReportDTO[];
  dots: DotDTO[];
  // A report fetched on demand because it wasn't in the loaded page (e.g. an old
  // report selected via a map dot). Rendered pinned at the top of the sidebar.
  pinnedReport: ReportDTO | null;
  activeReportId: number | null;
  pendingNewCount: number;
  loadedAt: string | null;
  eventTypeTotals: Record<string, number>;
  relevanceTotals: Record<string, number>;
  locationCounts: Record<string, number>;
  reloadTrigger: number;
  hasMore: boolean;
  totalCount: number;
  currentLimit: number;
  // Unseen high/medium reports matching the filters, counted server-side over the
  // WHOLE matching set (not just the loaded page). Synced only on explicit loads;
  // the optimistic actions below keep it responsive between loads.
  unseenCount: number;
  // True while a filter/search-driven reload is in flight (App.loadData), so the
  // UI can show a processing indicator instead of silently keeping stale results.
  isLoading: boolean;

  setReports: (reports: ReportDTO[], loadedAt: string, eventTypeTotals?: Record<string, number>, relevanceTotals?: Record<string, number>, hasMore?: boolean, locationCounts?: Record<string, number>, totalCount?: number, unseenCount?: number) => void;
  setUnseenCount: (n: number) => void;
  setIsLoading: (v: boolean) => void;
  bumpReloadTrigger: () => void;
  setCurrentLimit: (n: number) => void;
  setDots: (dots: DotDTO[]) => void;
  setPinnedReport: (report: ReportDTO | null) => void;
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
  pinnedReport: null,
  activeReportId: null,
  pendingNewCount: 0,
  loadedAt: null,
  eventTypeTotals: {},
  relevanceTotals: {},
  locationCounts: {},
  reloadTrigger: 0,
  hasMore: false,
  totalCount: 0,
  currentLimit: 50,
  unseenCount: 0,
  isLoading: false,

  setReports: (reports, loadedAt, eventTypeTotals = {}, relevanceTotals = {}, hasMore = false, locationCounts = {}, totalCount = 0, unseenCount = 0) => set({ reports, loadedAt, eventTypeTotals, relevanceTotals, hasMore, locationCounts, totalCount, unseenCount }),
  setUnseenCount: (unseenCount) => set({ unseenCount }),
  setIsLoading: (isLoading) => set({ isLoading }),
  bumpReloadTrigger: () => set((s) => ({ reloadTrigger: s.reloadTrigger + 1 })),
  setCurrentLimit: (currentLimit) => set({ currentLimit }),
  setDots: (dots) => set({ dots }),
  setPinnedReport: (pinnedReport) => set({ pinnedReport }),
  setActiveReportId: (id) => set({ activeReportId: id }),
  setPendingNewCount: (n) => set({ pendingNewCount: n }),

  optimisticHide: (id, hide) =>
    set((s) => {
      const target = s.reports.find((r) => r.id === id)
        ?? (s.pinnedReport?.id === id ? s.pinnedReport : null);
      // Hiding a new report removes it from the badge; unhiding one restores it.
      let unseenDelta = 0;
      if (target && target.user_state.new) {
        if (hide && !target.user_state.hide) unseenDelta = -1;
        else if (!hide && target.user_state.hide) unseenDelta = 1;
      }
      const patch = (r: ReportDTO) =>
        r.id === id ? { ...r, user_state: { ...r.user_state, hide } } : r;
      return {
        reports: s.reports.map(patch),
        pinnedReport: s.pinnedReport ? patch(s.pinnedReport) : null,
        dots: s.dots.map((d) => (d.report_id === id ? { ...d, seen: hide } : d)),
        unseenCount: Math.max(0, s.unseenCount + unseenDelta),
      };
    }),

  optimisticFlag: (author, flag) =>
    set((s) => {
      const patch = (r: ReportDTO) =>
        r.author === author
          ? {
              ...r,
              user_state: {
                ...r.user_state,
                flag,
                flag_author: flag ? author : null,
              },
            }
          : r;
      return {
        reports: s.reports.map(patch),
        pinnedReport: s.pinnedReport ? patch(s.pinnedReport) : null,
      };
    }),

  optimisticAcknowledge: (id) =>
    set((s) => {
      const target = s.reports.find((r) => r.id === id)
        ?? (s.pinnedReport?.id === id ? s.pinnedReport : null);
      const wasContributing = target ? contributesToUnseen(target) : false;
      const patch = (r: ReportDTO) =>
        r.id === id ? { ...r, user_state: { ...r.user_state, new: false } } : r;
      return {
        reports: s.reports.map(patch),
        pinnedReport: s.pinnedReport ? patch(s.pinnedReport) : null,
        dots: s.dots.map((d) => (d.report_id === id ? { ...d, new: false } : d)),
        unseenCount: wasContributing ? Math.max(0, s.unseenCount - 1) : s.unseenCount,
      };
    }),

  optimisticUpdateLocations: (id, locations) =>
    set((s) => {
      const patch = (r: ReportDTO) =>
        r.id === id
          ? { ...r, locations, user_state: { ...r.user_state, locations } }
          : r;
      return {
        reports: s.reports.map(patch),
        pinnedReport: s.pinnedReport ? patch(s.pinnedReport) : null,
      };
    }),

  optimisticRestoreLocations: (id, originalLocations) =>
    set((s) => {
      const patch = (r: ReportDTO) =>
        r.id === id
          ? {
              ...r,
              locations: originalLocations,
              user_state: { ...r.user_state, locations: null },
            }
          : r;
      return {
        reports: s.reports.map(patch),
        pinnedReport: s.pinnedReport ? patch(s.pinnedReport) : null,
      };
    }),
}));
