import { useMemo } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore } from '../store/useFilterStore';
import { useTourStore } from '../store/useTourStore';
import { exampleMatchesFilters } from '../tour/exampleReport';
import type { ReportDTO } from '../types';

/**
 * The reports actually shown in the sidebar list, after the "only new" client
 * view filter. Every server-side filter — platform, event type, relevance,
 * loc_filter, time, search, AND the drawn area (applied via PostGIS) — is already
 * applied to `reports`, so this only handles what the server can't see: the
 * optimistic hide gap and the tour example.
 *
 * Single source of truth so the header count always equals what the list renders
 * — ReportList and the Sidebar count both consume this.
 */
export function useVisibleReports(): ReportDTO[] {
  const reports = useReportStore((s) => s.reports);
  const activeReportId = useReportStore((s) => s.activeReportId);
  const showOnlyNew = useFilterStore((s) => s.showOnlyNew);
  const showHidden = useFilterStore((s) => s.showHidden);
  const activeExampleReportId = useTourStore((s) => s.activeExampleReportId);
  const filterState = useFilterStore();

  return useMemo(() => {
    let filtered = reports;

    // The example is always kept as a member of `reports` (see setReports) so
    // it can reappear the moment a search/filter change would match it again
    // — but it should only actually be VISIBLE when it currently does. It's
    // excluded from every real query, so the server can never do this filtering
    // for it the way it does for every other report; this replicates that here.
    if (activeExampleReportId !== null) {
      filtered = filtered.filter((r) => r.id !== activeExampleReportId || exampleMatchesFilters(r, filterState));
    }

    // With "show hidden" off, hiding a report should remove it from the list right
    // away (optimistically) rather than waiting for the next server reload — the
    // server already excludes hidden reports from `reports` in that mode, this just
    // covers the gap for a report hidden during the current session.
    //
    // Exception: the onboarding tour's example report stays in the list even if
    // hidden while the tour has it loaded. It still dims (ReportEntry already
    // does that for hide=true), but it can't disappear from the DOM — if it did,
    // whatever tour step is still pointing at it would lose its target and the
    // popover would jump to a fallback "centered" position mid-step.
    if (!showHidden) {
      filtered = filtered.filter((r) => !r.user_state.hide || r.id === activeExampleReportId);
    }

    if (showOnlyNew) {
      // Keep the selected report even after clicking it acknowledged it, so it
      // doesn't vanish from under you while you're viewing it on the map. It
      // drops out once you select something else.
      filtered = filtered.filter((r) => r.user_state.new || r.id === activeReportId);
    }

    return filtered;
  }, [reports, showOnlyNew, activeReportId, showHidden, activeExampleReportId, filterState]);
}
