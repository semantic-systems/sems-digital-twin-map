import { create } from 'zustand';
import type { ReportDTO, DotDTO, LocationEntry, DotsParams } from '../types';
import { fetchDots } from '../api/reports';
import { useTourStore } from './useTourStore';

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

  // The onboarding tour's example report (see tour/exampleReport.ts) — a real
  // `reports` entry so every real handler (hide/flag/acknowledge/place-a-location)
  // works natively with zero special-casing. Its map dots are deliberately NOT
  // stored here — useVisibleDots derives them live from this report's own
  // locations instead (see exampleReport.ts's deriveExampleDots), because
  // `dots` gets wholesale-replaced by any real refreshDots() call (including
  // the one the location-edit flow itself triggers on success), which would
  // otherwise wipe the example's dots the moment a location is actually placed.
  addExampleReport: (report: ReportDTO) => void;
  removeExampleReport: (id: number) => void;

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
  currentLimit: 200,
  unseenCount: 0,
  isLoading: false,

  // Facet totals (eventTypeTotals/relevanceTotals/locationCounts) are preserved
  // when omitted (undefined) — the "only new" lean load skips recomputing them and
  // reuses the last-known panel counts. Pass {} explicitly to actually clear them.
  setReports: (reports, loadedAt, eventTypeTotals, relevanceTotals, hasMore = false, locationCounts, totalCount = 0, unseenCount = 0) =>
    set((s) => {
      // The tour's example report is deliberately excluded from every real
      // query (backend report_service.build_report_query), so a real reload
      // — including one the tour's own "search"/"filter bar" steps actively
      // invite the user to trigger — would otherwise silently drop it out of
      // `reports` entirely. Always re-attach it here regardless of whether it
      // currently matches the active filters (carrying forward whatever the
      // user has done to it — hide/flag/a new location — not the pre-load
      // snapshot): this is the only place the object itself is kept, so
      // dropping it here for not matching would lose it for good — a later
      // filter change that WOULD match it again would have nothing left to
      // bring back. Whether it's actually visible right now is decided at
      // read time instead (useVisibleReports/useVisibleDots), same as every
      // other filter already works.
      const exampleId = useTourStore.getState().activeExampleReportId;
      const example = exampleId !== null ? s.reports.find((r) => r.id === exampleId) : undefined;
      const withExample = example && !reports.some((r) => r.id === exampleId)
        ? [example, ...reports]
        : reports;
      return {
        reports: withExample,
        loadedAt,
        hasMore,
        totalCount,
        unseenCount,
        eventTypeTotals: eventTypeTotals ?? s.eventTypeTotals,
        relevanceTotals: relevanceTotals ?? s.relevanceTotals,
        locationCounts: locationCounts ?? s.locationCounts,
      };
    }),
  setUnseenCount: (unseenCount) => set({ unseenCount }),
  setIsLoading: (isLoading) => set({ isLoading }),
  bumpReloadTrigger: () => set((s) => ({ reloadTrigger: s.reloadTrigger + 1 })),
  setCurrentLimit: (currentLimit) => set({ currentLimit }),
  setDots: (dots) => set({ dots }),
  setPinnedReport: (pinnedReport) => set({ pinnedReport }),
  setActiveReportId: (id) => set({ activeReportId: id }),
  setPendingNewCount: (n) => set({ pendingNewCount: n }),

  addExampleReport: (report) =>
    set((s) => ({
      reports: [report, ...s.reports.filter((r) => r.id !== report.id)],
    })),
  removeExampleReport: (id) =>
    set((s) => ({
      reports: s.reports.filter((r) => r.id !== id),
      pinnedReport: s.pinnedReport?.id === id ? null : s.pinnedReport,
    })),

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

// ---------------------------------------------------------------------------
// Shared dots-refresh ordering guard
// ---------------------------------------------------------------------------
//
// Several independent places fetch and apply a fresh `dots` array: the 10s
// auto-update poll's reload, a location edit (pin-set / map-drag) in
// PickModeOverlay/MapView, ReportEntry's "restore locations", and App.loadData's
// combined reports+dots bundle. Each is its own async round trip; with no shared
// ordering guard, two overlapping refreshes (e.g. auto-update firing while a
// location edit is in flight) let whichever response simply ARRIVES last win,
// even if it was the one that started FIRST and is therefore stale — the same
// class of race already fixed once for the report-acknowledge/poll interaction.
// `dotsRequestSeq` is module-level (not store state): it's a private ordering
// token, not UI state, so it doesn't belong in the reactive store shape.
let dotsRequestSeq = 0;

/** Call before starting a dots fetch; returns a token identifying this attempt. */
export function beginDotsRefresh(): number {
  return ++dotsRequestSeq;
}

/** Applies `dots` only if no newer refresh has started since `token` was issued. */
export function commitDotsIfCurrent(dots: DotDTO[], token: number): void {
  if (token !== dotsRequestSeq) return;
  useReportStore.setState({ dots });
}

/** Fetch + apply in one step for the common case (no separate reports payload
 *  arriving alongside). Prefer this over calling fetchDots + setDots directly. */
export async function refreshDots(params: DotsParams): Promise<void> {
  const token = beginDotsRefresh();
  const res = await fetchDots(params);
  commitDotsIfCurrent(res.dots, token);
}
