import { useMemo } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore } from '../store/useFilterStore';
import { pointInPolygon } from '../utils/geo';
import { exampleFacetContribution } from '../tour/exampleReport';
import { EXAMPLE_IDENTIFIER as TOUR_EXAMPLE_IDENTIFIER } from '../tour/constants';
import type { DotDTO, ReportDTO } from '../types';

function bump(counts: Record<string, number>, key: string | null): Record<string, number> {
  return key ? { ...counts, [key]: (counts[key] ?? 0) + 1 } : counts;
}

/**
 * Adjust a server-side report count for the drawn-area (spatial) filter, which
 * is the one filter applied purely client-side and so is NOT reflected in the
 * server's total. The dots array is the full set of location points, already
 * filtered server-side by every OTHER filter, so we don't re-request anything:
 * the only reports the polygon should remove are those that HAVE coordinates
 * but none inside it. `count − (reports_with_any_dot − reports_with_an_in_area_dot)`.
 * No-coords reports have no dots, so they're never subtracted — they keep the
 * "can't be spatially disproven, so they pass" semantics the list uses.
 *
 * unseenBasis restricts to the unseen set (dots that are new and not hidden),
 * because the server's unseen_count always excludes hidden reports even when
 * show-hidden is on.
 */
function spatialAdjust(
  count: number,
  dots: DotDTO[],
  polygon: [number, number][],
  unseenBasis: boolean,
): number {
  const basis = unseenBasis ? dots.filter((d) => d.new && !d.seen) : dots;
  const withAnyDot = new Set(basis.map((d) => d.report_id));
  const withInAreaDot = new Set(
    basis.filter((d) => pointInPolygon(d.lat, d.lon, polygon)).map((d) => d.report_id),
  );
  return Math.max(0, count - (withAnyDot.size - withInAreaDot.size));
}

/** Whether the tour example passes the drawn-area filter — mirrors useVisibleReports:
 *  no coordinates → always passes; otherwise at least one point inside the polygon. */
function exampleInArea(example: ReportDTO, polygon: [number, number][]): boolean {
  const locs = example.user_state.locations ?? example.locations;
  const coords = locs.filter((l) => l.lat != null && l.lon != null);
  if (coords.length === 0) return true;
  return coords.some((l) => pointInPolygon(l.lat as number, l.lon as number, polygon));
}

/**
 * The little "(N)" counts next to each filter checkbox/chip, plus the header's
 * total/unseen counts. Two adjustments layer on top of the raw server numbers:
 *
 *  - the onboarding tour's example report is excluded from every real query
 *    (build_report_query), so it's added back here wherever it currently applies;
 *  - the drawn-area (spatial) filter is applied client-side only, so the header
 *    total/unseen — which come from the server, which never saw the polygon —
 *    are corrected here from the dots (see spatialAdjust). The per-checkbox facet
 *    counts are intentionally left at the server's area-independent distribution.
 */
export function useEffectiveFacetTotals() {
  const reports = useReportStore((s) => s.reports);
  const dots = useReportStore((s) => s.dots);
  const eventTypeTotals = useReportStore((s) => s.eventTypeTotals);
  const relevanceTotals = useReportStore((s) => s.relevanceTotals);
  const locationCounts = useReportStore((s) => s.locationCounts);
  const unseenCount = useReportStore((s) => s.unseenCount);
  const totalCount = useReportStore((s) => s.totalCount);
  const platformCounts = useFilterStore((s) => s.platformCounts);
  const spatialPolygon = useFilterStore((s) => s.spatialPolygon);
  const filterState = useFilterStore();

  return useMemo(() => {
    // Header totals: start from the server number, correct for the drawn area.
    let effTotalCount = spatialPolygon ? spatialAdjust(totalCount, dots, spatialPolygon, false) : totalCount;
    let effUnseenCount = spatialPolygon ? spatialAdjust(unseenCount, dots, spatialPolygon, true) : unseenCount;

    const example = reports.find((r) => r.identifier === TOUR_EXAMPLE_IDENTIFIER);
    if (!example) {
      return { eventTypeTotals, relevanceTotals, locationCounts, platformCounts, unseenCount: effUnseenCount, totalCount: effTotalCount };
    }

    const c = exampleFacetContribution(example, filterState);
    // The example isn't in `dots` (its dots are derived separately), so the
    // spatial adjustment above never saw it — gate its header contribution on
    // its own area membership when a polygon is active.
    const exampleInDrawnArea = !spatialPolygon || exampleInArea(example, spatialPolygon);
    if (c.countsAsTotal && exampleInDrawnArea) effTotalCount += 1;
    if (c.countsAsUnseen && exampleInDrawnArea) effUnseenCount += 1;

    let effEventTypeTotals = eventTypeTotals;
    for (const et of c.eventTypes) effEventTypeTotals = bump(effEventTypeTotals, et);

    return {
      eventTypeTotals: effEventTypeTotals,
      relevanceTotals: bump(relevanceTotals, c.relevance),
      locationCounts: bump(locationCounts, c.locationStatus),
      platformCounts: bump(platformCounts, c.platform),
      unseenCount: effUnseenCount,
      totalCount: effTotalCount,
    };
  }, [reports, dots, eventTypeTotals, relevanceTotals, locationCounts, platformCounts, unseenCount, totalCount, spatialPolygon, filterState]);
}