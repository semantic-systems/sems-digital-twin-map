import { useMemo } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore } from '../store/useFilterStore';
import { pointInPolygon } from '../utils/geo';
import type { ReportDTO } from '../types';

/**
 * The reports actually shown in the sidebar list, after the client-side view
 * filters (spatial polygon + "only new"). Server-side filters (platform, event
 * type, relevance, loc_filter, time, search) are already applied to `reports`.
 *
 * Single source of truth so the header count always equals what the list renders
 * — ReportList and the Sidebar count both consume this.
 */
export function useVisibleReports(): ReportDTO[] {
  const reports = useReportStore((s) => s.reports);
  const activeReportId = useReportStore((s) => s.activeReportId);
  const spatialPolygon = useFilterStore((s) => s.spatialPolygon);
  const showOnlyNew = useFilterStore((s) => s.showOnlyNew);
  const showHidden = useFilterStore((s) => s.showHidden);

  return useMemo(() => {
    let filtered = reports;

    // With "show hidden" off, hiding a report should remove it from the list right
    // away (optimistically) rather than waiting for the next server reload — the
    // server already excludes hidden reports from `reports` in that mode, this just
    // covers the gap for a report hidden during the current session.
    if (!showHidden) {
      filtered = filtered.filter((r) => !r.user_state.hide);
    }

    if (showOnlyNew) {
      // Keep the selected report even after clicking it acknowledged it, so it
      // doesn't vanish from under you while you're viewing it on the map. It
      // drops out once you select something else.
      filtered = filtered.filter((r) => r.user_state.new || r.id === activeReportId);
    }

    // Spatial polygon filter — reports with no coordinates always pass
    // (they can't be spatially disproven, and may well be relevant).
    if (spatialPolygon) {
      filtered = filtered.filter((r) => {
        const locs = r.user_state.locations ?? r.locations;
        const hasCoords = locs.some((l) => l.lat != null && l.lon != null);
        if (!hasCoords) return true;
        return locs.some(
          (l) =>
            l.lat != null &&
            l.lon != null &&
            pointInPolygon(l.lat as number, l.lon as number, spatialPolygon),
        );
      });
    }

    return filtered;
  }, [reports, spatialPolygon, showOnlyNew, activeReportId, showHidden]);
}
