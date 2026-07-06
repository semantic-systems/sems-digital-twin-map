import { useMemo } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore } from '../store/useFilterStore';
import { pointInPolygon, computeSuppressedDotsWithLocs } from '../utils/geo';
import type { DotDTO } from '../types';

/**
 * The dots actually shown on the map, after every active filter: seen/hidden
 * (respecting showHidden), the drawn spatial filter, "only new", and containment
 * suppression. Single source of truth so anything that draws per-location map
 * overlays (dots, polygons) reads the SAME visibility decision — a location whose
 * dot doesn't survive here can't independently keep its polygon on screen either.
 */
export function useVisibleDots(): DotDTO[] {
  const dots = useReportStore((s) => s.dots);
  const activeReportId = useReportStore((s) => s.activeReportId);
  const reports = useReportStore((s) => s.reports);
  const showHidden = useFilterStore((s) => s.showHidden);
  const spatialPolygon = useFilterStore((s) => s.spatialPolygon);
  const showOnlyNew = useFilterStore((s) => s.showOnlyNew);

  return useMemo(() => {
    const hiddenIds = showHidden
      ? new Set<number>()
      : new Set(reports.filter((r) => r.user_state.hide).map((r) => r.id));
    let result = showHidden
      ? dots
      : dots.filter((d) => !d.seen && !hiddenIds.has(d.report_id));
    if (spatialPolygon) {
      result = result.filter((d) => pointInPolygon(d.lat, d.lon, spatialPolygon));
    }
    if (showOnlyNew) {
      // Keep the selected report's dots even after acknowledging cleared their
      // new flag, so the report you just clicked stays visible on the map.
      result = result.filter((d) => d.new || d.report_id === activeReportId);
    }
    // Containment suppression: for each report, hide dots whose location polygon
    // contains another dot of the same report (i.e. they are a spatial superset).
    const byReport = new Map<number, typeof result>();
    for (const d of result) {
      if (!byReport.has(d.report_id)) byReport.set(d.report_id, []);
      byReport.get(d.report_id)!.push(d);
    }
    const suppressed = new Set<(typeof result)[0]>();
    for (const [reportId, group] of byReport.entries()) {
      if (group.length > 1) {
        const report = reports.find((r) => r.id === reportId);
        const locs = report ? (report.user_state.locations ?? report.locations ?? []) : [];
        for (const d of computeSuppressedDotsWithLocs(group, locs)) suppressed.add(d);
      }
    }
    return result.filter((d) => !suppressed.has(d));
  }, [dots, showHidden, reports, spatialPolygon, showOnlyNew, activeReportId]);
}
