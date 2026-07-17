import type { ReportDTO, DotDTO } from '../types';
import { fetchTourExample } from '../api/reports';
export * from './constants';

import { activeLocFilter, ALL_EVENT_TYPES_LIST, ALL_RELEVANCES_LIST } from '../store/useFilterStore';

/** Fetches the example report, admitting it for `username` as a side effect (see backend). */
export async function loadExampleReport(username: string): Promise<ReportDTO> {
  return fetchTourExample(username);
}

const TIME_WINDOW_HOURS: Record<string, number> = { '1h': 1, '6h': 6, '1d': 24, '3d': 72 };

/** Mirrors reports.py's `_since_from_window` / custom-range resolution. */
function timeWindowSince(timeWindow: string, customSince: string | null): Date | null {
  if (timeWindow === 'custom') {
    return customSince ? new Date(customSince) : null;
  }
  const hours = TIME_WINDOW_HOURS[timeWindow];
  return hours ? new Date(Date.now() - hours * 3_600_000) : null; // 'all' (or unknown) = no bound
}

/**
 * Would this report have matched the currently active search/filter state?
 * The example is excluded from every real query (see build_report_query), so
 * the backend can never answer this for us — without this check, a `setReports`
 * re-attach (see useReportStore) would make it immune to filtering and search
 * entirely, which is exactly backwards: it's supposed to behave like a real
 * report, including disappearing when it genuinely doesn't match. Mirrors the
 * filter semantics in backend/app/services/report_service.py.
 * 
 * @param filterState - Filter state from useFilterStore.getState(). Pass here
 *   rather than calling getState() inside to avoid stale closure issues.
 */
export function exampleMatchesFilters(
  example: ReportDTO,
  filterState: { platforms: string[]; allPlatforms: string[]; eventTypes: string[]; relevances: string[]; search: string; timeWindow: string; customSince: string | null; customUntil: string | null; showHidden: boolean; showFlagged: boolean; showUnflagged: boolean; locShowLocalized: boolean; locShowPending: boolean; locShowUnlocalized: boolean }
): boolean {
  const f = filterState;

  if (!passesBaseFilters(example, f)) return false;

  // Platform — prefix match (mirrors Report.platform.like(f"{p}%")). An empty
  // selection means "all" (App.tsx sends allPlatforms in that case).
  const effPlatforms = f.platforms.length ? f.platforms : f.allPlatforms;
  if (effPlatforms.length && !effPlatforms.some((p) => example.platform.startsWith(p))) {
    return false;
  }

  // Event type / relevance — "all selected" means no filter (normalize_filters).
  const allEventTypesSelected = ALL_EVENT_TYPES_LIST.every((t) => f.eventTypes.includes(t));
  if (f.eventTypes.length && !allEventTypesSelected) {
    if (!example.event_types.some((t) => f.eventTypes.includes(t))) return false;
  }
  const allRelevancesSelected = ALL_RELEVANCES_LIST.every((r) => f.relevances.includes(r));
  if (f.relevances.length && !allRelevancesSelected) {
    if (!f.relevances.includes(example.relevance)) return false;
  }

  // Location type. The example's locations carry lat/lon but no osm_id, so the
  // backend would classify them as "pending", not "localized" — even though
  // the frontend's own isLocationConfirmed() treats lat/lon alone as enough to
  // render the green "confirmed" tag style. Matching backend semantics here
  // since this check exists to mirror what the server would have decided.
  const locFilter = activeLocFilter(f);
  if (locFilter && !locFilter.includes(exampleLocationStatus(example))) return false;

  // Flagged/unflagged. Not showHidden — the example deliberately stays visible
  // (dimmed) while hidden regardless of that filter; see useVisibleReports.
  const isFlagged = example.user_state.flag;
  if (isFlagged && !f.showFlagged) return false;
  if (!isFlagged && !f.showUnflagged) return false;

  return true;
}

/** The example's location-type bucket, mirroring get_reports'/build_dots' osm_id-based classification. */
function exampleLocationStatus(example: ReportDTO): 'localized' | 'pending' | 'unlocalized' {
  const locs = example.user_state.locations ?? example.locations;
  const isLocalized = locs.some((l) => !!l.osm_id);
  if (isLocalized) return 'localized';
  return locs.length > 0 ? 'pending' : 'unlocalized';
}

/**
 * Whether the example passes the filters that gate the facet-count loop
 * entirely in get_reports (base query filters + hide/flag), independent of
 * any single facet dimension. Shared by exampleMatchesFilters and
 * exampleFacetContribution so the two can't drift apart.
 */
function passesBaseFilters(example: ReportDTO, f: { search: string; timeWindow: string; customSince: string | null; customUntil: string | null }): boolean {
  if (f.search) {
    const term = f.search.toLowerCase();
    const inText = example.text.toLowerCase().includes(term);
    const inAuthor = (example.author ?? '').toLowerCase().includes(term);
    if (!inText && !inAuthor) return false;
  }
  const since = timeWindowSince(f.timeWindow, f.customSince);
  const until = f.timeWindow === 'custom' && f.customUntil ? new Date(f.customUntil) : null;
  const ts = new Date(example.timestamp);
  if (since && ts < since) return false;
  if (until && ts > until) return false;
  return true;
}

export interface ExampleFacetContribution {
  eventTypes: string[];
  relevance: string | null;
  platform: string | null;
  locationStatus: 'localized' | 'pending' | 'unlocalized' | null;
  countsAsUnseen: boolean;
  countsAsTotal: boolean;
}

const NO_CONTRIBUTION: ExampleFacetContribution = {
  eventTypes: [], relevance: null, platform: null, locationStatus: null,
  countsAsUnseen: false, countsAsTotal: false,
};

/**
 * Which facet-count buckets (the small "(N)" next to each filter checkbox/chip)
 * the example should contribute to. The counts are server-computed and the
 * example is excluded from every real query (build_report_query), so without
 * this the panel would silently undercount by one wherever the example
 * currently applies — e.g. showing "High (3)" while a 4th (the example) is
 * plainly visible in the list. Mirrors get_reports' cross-filtered facet loop:
 * each dimension's count reflects every OTHER active filter but not itself.
 * 
 * @param filterState - Filter state from useFilterStore.getState(). Pass here
 *   rather than calling getState() inside to avoid stale closure issues.
 */
export function exampleFacetContribution(
  example: ReportDTO,
  filterState: { platforms: string[]; allPlatforms: string[]; eventTypes: string[]; relevances: string[]; search: string; timeWindow: string; customSince: string | null; customUntil: string | null; showHidden: boolean; showFlagged: boolean; showUnflagged: boolean; locShowLocalized: boolean; locShowPending: boolean; locShowUnlocalized: boolean }
): ExampleFacetContribution {
  const f = filterState;

  // Mirrors "if not show_hidden and rid in seen_ids: continue" — hidden
  // reports drop out of facet counting entirely unless show_hidden is on
  // (unlike exampleMatchesFilters' visibility check, which deliberately
  // ignores this so the card doesn't vanish mid-tour — these are just
  // informational tallies, not a DOM-presence decision).
  if (example.user_state.hide && !f.showHidden) return NO_CONTRIBUTION;
  const isFlagged = example.user_state.flag;
  if (!f.showFlagged && isFlagged) return NO_CONTRIBUTION;
  if (!f.showUnflagged && !isFlagged) return NO_CONTRIBUTION;
  if (!passesBaseFilters(example, f)) return NO_CONTRIBUTION;

  const effPlatforms = f.platforms.length ? f.platforms : f.allPlatforms;
  const allEventTypesSelected = ALL_EVENT_TYPES_LIST.every((t) => f.eventTypes.includes(t));
  const effEvents = f.eventTypes.length && !allEventTypesSelected ? f.eventTypes : null;
  const allRelevancesSelected = ALL_RELEVANCES_LIST.every((r) => f.relevances.includes(r));
  const effRelevances = f.relevances.length && !allRelevancesSelected ? f.relevances : null;
  const effLoc = activeLocFilter(f);

  const passesPlat = !effPlatforms.length || effPlatforms.some((p) => example.platform.startsWith(p));
  const passesEvt = !effEvents || example.event_types.some((t) => effEvents.includes(t));
  const passesRel = !effRelevances || effRelevances.includes(example.relevance);
  const locationStatus = exampleLocationStatus(example);
  const passesLoc = !effLoc || effLoc.includes(locationStatus);

  return {
    eventTypes: passesPlat && passesRel && passesLoc ? example.event_types : [],
    relevance: passesPlat && passesEvt && passesLoc ? example.relevance : null,
    platform: passesEvt && passesRel && passesLoc ? example.platform : null,
    locationStatus: passesPlat && passesEvt && passesRel ? locationStatus : null,
    countsAsUnseen: example.user_state.new && passesPlat && passesEvt && passesRel && passesLoc,
    countsAsTotal: passesPlat && passesEvt && passesRel && passesLoc,
  };
}

/** Derives map dots straight from the report's own locations — one per location, no backend round trip. */
export function deriveExampleDots(report: ReportDTO): DotDTO[] {
  const { hide, flag, new: isNew } = report.user_state;
  const locs = report.user_state.locations ?? report.locations;
  return locs
    .filter((l) => l.lat != null && l.lon != null)
    .map((l) => ({
      report_id: report.id,
      lat: l.lat as number,
      lon: l.lon as number,
      seen: hide,
      hide,
      flag,
      new: isNew,
      location_name: l.name ?? l.display_name ?? '',
      location_display: l.mention ?? '',
      text: report.text,
      author: report.author ?? '',
      platform: report.platform,
      timestamp: report.timestamp,
      event_types: report.event_types,
      relevance: report.relevance,
      url: report.url,
      location_bbox_area: null,
      location_bbox: null,
    }));
}
