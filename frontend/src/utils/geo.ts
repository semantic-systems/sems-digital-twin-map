import type { LocationEntry, DotDTO } from '../types';

// (Point-in-polygon lived here; the drawn-area filter is now applied server-side
// via PostGIS, so no client-side geometry test is needed.)

// Short OSM type codes (Photon) vs. long ones (Nominatim) — normalize so the same
// entity written both ways ("R" vs "relation") collapses to one key.
const OSM_TYPE_CANON: Record<string, string> = { R: 'relation', N: 'node', W: 'way' };
export const osmKey = (l: LocationEntry): string =>
  `${l.osm_id}:${OSM_TYPE_CANON[l.osm_type ?? ''] ?? l.osm_type ?? ''}`;

/** Drop entries that are the SAME OSM entity (all rendered entries have an osm_id),
 * so a place referenced by two mentions isn't drawn twice. A no-op when there are
 * no duplicates. Generic so it preserves the caller's element type. */
export function dedupByOsm<T extends LocationEntry>(locs: T[]): T[] {
  const seen = new Set<string>();
  return locs.filter((l) => {
    const k = osmKey(l);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

/** A location is "confirmed" once it has real coordinates — either geocoded via
 * OSM (osm_id) or pinned directly on the map (lat/lon only). Only a bare mention
 * with neither is still "pending". */
export function isLocationConfirmed(loc: LocationEntry): boolean {
  return Boolean(loc.osm_id) || (loc.lat != null && loc.lon != null);
}

export type Bbox = [number, number, number, number]; // [minLat, maxLat, minLon, maxLon]

/**
 * Bounding box [minLat, maxLat, minLon, maxLon] of a location's geometry — polygon,
 * line, or Nominatim boundingbox — or a degenerate box at its point. Returns null
 * when no coordinates are available. This is the single spatial extent used for
 * containment, so dots and polygons always agree on a location's size.
 */
export function locationExtent(loc: LocationEntry): Bbox | null {
  // Extent over the WHOLE polygon/line geometry (every ring/part), so it matches
  // what actually renders. Point geometries are skipped — their stored coordinate
  // order is unreliable — and covered by the authoritative lat/lon fallback below.
  const p = loc.polygon;
  if (p && p.type !== 'Point' && p.coordinates != null) {
    const bbox = coordsBbox(p.coordinates);
    if (bbox) return bbox;
  }
  if (Array.isArray(loc.boundingbox) && loc.boundingbox.length === 4) {
    const [minLat, maxLat, minLon, maxLon] = (loc.boundingbox as unknown[]).map(Number);
    return [minLat, maxLat, minLon, maxLon];
  }
  if (loc.lat != null && loc.lon != null) {
    const lat = Number(loc.lat), lon = Number(loc.lon);
    if (!Number.isNaN(lat) && !Number.isNaN(lon)) return [lat, lat, lon, lon];
  }
  return null;
}

/**
 * Single source of truth for containment suppression. Given one bounding box per
 * region (a dot, or a polygon location) of the SAME report, returns the indices of
 * regions to hide because another region's box is strictly contained within theirs —
 * i.e. they are the less-specific spatial superset (e.g. "Hamburg" when "Rahlstedt"
 * is also present). Pure bbox-in-bbox containment; identical boxes (the same place
 * listed twice) suppress neither. Both ReportDots and ActiveReportPolygons consume
 * this so a location is always shown as dot+polygon together, or hidden together.
 */
export function computeSuppressedRegions(boxes: (Bbox | null)[]): Set<number> {
  const suppressed = new Set<number>();
  for (let i = 0; i < boxes.length; i++) {
    const a = boxes[i];
    if (!a || suppressed.has(i)) continue;
    for (let j = 0; j < boxes.length; j++) {
      if (i === j) continue;
      const b = boxes[j];
      if (!b) continue;
      const bInsideA = b[0] >= a[0] && b[1] <= a[1] && b[2] >= a[2] && b[3] <= a[3];
      if (!bInsideA) continue;
      // Identical extents (same place twice, or two nodes at one point) are not a
      // superset relationship — keep both.
      const identical = a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3];
      if (identical) continue;
      // b is strictly inside a → a is the broader superset → hide a.
      suppressed.add(i);
      break;
    }
  }
  return suppressed;
}

/**
 * Bounding box [minLat, maxLat, minLon, maxLon] over EVERY [lon, lat] coordinate
 * pair in a GeoJSON `coordinates` value, at any nesting depth (Polygon, MultiPolygon,
 * LineString, …). Using the whole geometry — not just the first/largest ring — is
 * deliberate: a polygon's first ring can be an unrepresentative fragment (e.g.
 * mis-ordered multipolygon rings), which would otherwise shrink an area's extent to
 * a sliver and defeat containment suppression.
 */
function coordsBbox(coords: unknown): Bbox | null {
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  const walk = (node: unknown): void => {
    if (!Array.isArray(node)) return;
    if (typeof node[0] === 'number' && typeof node[1] === 'number') {
      const lon = node[0] as number, lat = node[1] as number;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
      return;
    }
    for (const child of node) walk(child);
  };
  walk(coords);
  if (minLat === Infinity) return null;
  return [minLat, maxLat, minLon, maxLon];
}

/** ~11 m — the lat/lon proximity tolerance used to match a LocationEntry to the
 *  dot built from it (build_dots sets dot.lat/lon directly from loc.lat/lon). */
const LOCATION_DOT_MATCH_TOLERANCE = 1e-4;

function locationMatchesDot(loc: LocationEntry, d: DotDTO): boolean {
  return (
    loc.lat != null &&
    loc.lon != null &&
    Math.abs(Number(loc.lat) - d.lat) < LOCATION_DOT_MATCH_TOLERANCE &&
    Math.abs(Number(loc.lon) - d.lon) < LOCATION_DOT_MATCH_TOLERANCE
  );
}

/**
 * Restricts a report's locations to those with a corresponding LIVE dot in
 * `visibleDots` (same report_id, matching lat/lon). A polygon can only be attached
 * to an existing, currently-visible dot — so a location whose dot was filtered out
 * (hidden, outside the drawn spatial filter, "only new", etc.) is excluded here
 * before any polygon rendering or containment suppression runs. This is what binds
 * polygon visibility to dot visibility instead of the two being decided separately.
 */
export function filterLocationsWithVisibleDots(
  locs: LocationEntry[],
  reportId: number,
  visibleDots: DotDTO[],
): LocationEntry[] {
  const reportDots = visibleDots.filter((d) => d.report_id === reportId);
  if (reportDots.length === 0) return [];
  return locs.filter((loc) => reportDots.some((d) => locationMatchesDot(loc, d)));
}

/**
 * Returns the dots hidden by containment suppression. Each dot's spatial extent is
 * the polygon-derived `location_bbox` when available, else its matched location's
 * geometry, else a point. Delegates to computeSuppressedRegions so dot suppression
 * is identical to polygon suppression. `locs` is the report's effective location
 * list (user_state.locations ?? locations).
 */
export function computeSuppressedDotsWithLocs(
  groupDots: DotDTO[],
  locs: LocationEntry[],
): Set<DotDTO> {
  const boxes: (Bbox | null)[] = groupDots.map((d) => {
    if (d.location_bbox) return d.location_bbox;
    const loc = locs.find((l) => locationMatchesDot(l, d));
    const ext = loc ? locationExtent(loc) : null;
    return ext ?? [d.lat, d.lat, d.lon, d.lon];
  });

  const suppressedIdx = computeSuppressedRegions(boxes);
  const result = new Set<DotDTO>();
  suppressedIdx.forEach((i) => result.add(groupDots[i]));
  return result;
}

/**
 * Compute the map bounds that frame only the *visible* (non-suppressed) dots of a
 * single report, applying the same containment suppression as ReportDots so a
 * superset location (e.g. a whole country) does not stretch the view. Each dot
 * contributes its full polygon extent (location_bbox) when known, else a small box
 * around its point. Returns [[south, west], [north, east]] or null if nothing to frame.
 */
export function computeVisibleReportBounds(
  reportDots: DotDTO[],
  locs: LocationEntry[],
): [[number, number], [number, number]] | null {
  let visibleDots = reportDots;
  if (reportDots.length > 1) {
    const suppressed = computeSuppressedDotsWithLocs(reportDots, locs);
    visibleDots = reportDots.filter((d) => !suppressed.has(d));
  }

  let south = Infinity, north = -Infinity, west = Infinity, east = -Infinity;
  for (const d of visibleDots) {
    if (d.location_bbox) {
      // location_bbox: [min_lat, max_lat, min_lon, max_lon]
      south = Math.min(south, d.location_bbox[0]);
      north = Math.max(north, d.location_bbox[1]);
      west  = Math.min(west,  d.location_bbox[2]);
      east  = Math.max(east,  d.location_bbox[3]);
    } else {
      south = Math.min(south, d.lat - 0.01);
      north = Math.max(north, d.lat + 0.01);
      west  = Math.min(west,  d.lon - 0.01);
      east  = Math.max(east,  d.lon + 0.01);
    }
  }

  if (south === Infinity) return null;
  return [[south, west], [north, east]];
}
