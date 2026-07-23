import { useMemo } from 'react';
import { useReportStore } from '../store/useReportStore';
import { useFilterStore } from '../store/useFilterStore';
import { exampleFacetContribution } from '../tour/exampleReport';
import { EXAMPLE_IDENTIFIER as TOUR_EXAMPLE_IDENTIFIER } from '../tour/constants';

function bump(counts: Record<string, number>, key: string | null): Record<string, number> {
  return key ? { ...counts, [key]: (counts[key] ?? 0) + 1 } : counts;
}

/**
 * The little "(N)" counts next to each filter checkbox/chip, plus the header's
 * total/unseen counts, adjusted to include the onboarding tour's example report.
 * The example is excluded from every real query (build_report_query), so without
 * this the panel would silently undercount by one wherever the example currently
 * applies. Every real filter — including the drawn area, now applied server-side
 * via PostGIS — is already reflected in the raw server counts, so there is no
 * client-side count correction to do here anymore.
 */
export function useEffectiveFacetTotals() {
  const reports = useReportStore((s) => s.reports);
  const eventTypeTotals = useReportStore((s) => s.eventTypeTotals);
  const relevanceTotals = useReportStore((s) => s.relevanceTotals);
  const locationCounts = useReportStore((s) => s.locationCounts);
  const unseenCount = useReportStore((s) => s.unseenCount);
  const totalCount = useReportStore((s) => s.totalCount);
  const platformCounts = useFilterStore((s) => s.platformCounts);
  const filterState = useFilterStore();

  return useMemo(() => {
    const example = reports.find((r) => r.identifier === TOUR_EXAMPLE_IDENTIFIER);
    if (!example) {
      return { eventTypeTotals, relevanceTotals, locationCounts, platformCounts, unseenCount, totalCount };
    }

    const c = exampleFacetContribution(example, filterState);
    let effEventTypeTotals = eventTypeTotals;
    for (const et of c.eventTypes) effEventTypeTotals = bump(effEventTypeTotals, et);

    return {
      eventTypeTotals: effEventTypeTotals,
      relevanceTotals: bump(relevanceTotals, c.relevance),
      locationCounts: bump(locationCounts, c.locationStatus),
      platformCounts: bump(platformCounts, c.platform),
      unseenCount: unseenCount + (c.countsAsUnseen ? 1 : 0),
      totalCount: totalCount + (c.countsAsTotal ? 1 : 0),
    };
  }, [reports, eventTypeTotals, relevanceTotals, locationCounts, platformCounts, unseenCount, totalCount, filterState]);
}
