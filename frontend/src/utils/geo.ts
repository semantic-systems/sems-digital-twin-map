import type { LocationEntry, DotDTO } from '../types';

/** Ray-casting point-in-polygon. Polygon is an array of [lat, lon] pairs. */
export function pointInPolygon(lat: number, lon: number, polygon: [number, number][]): boolean {
  let inside = false;
  const n = polygon.length;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const [yi, xi] = polygon[i];
    const [yj, xj] = polygon[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** Bounding-box area in degrees² for a [lat, lon][] polygon. */
export function polygonBboxArea(polygon: [number, number][]): number {
  if (polygon.length === 0) return 0;
  let minLat = polygon[0][0], maxLat = polygon[0][0];
  let minLon = polygon[0][1], maxLon = polygon[0][1];
  for (const [lat, lon] of polygon) {
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
  }
  return (maxLat - minLat) * (maxLon - minLon);
}

export type Bbox = [number, number, number, number]; // [minLat, maxLat, minLon, maxLon]

/**
 * Bounding box [minLat, maxLat, minLon, maxLon] of a location's geometry — polygon,
 * line, or Nominatim boundingbox — or a degenerate box at its point. Returns null
 * when no coordinates are available. This is the single spatial extent used for
 * containment, so dots and polygons always agree on a location's size.
 */
export function locationExtent(loc: LocationEntry): Bbox | null {
  const ring = getLocationRing(loc);
  if (ring && ring.length > 0) {
    let minLat = ring[0][0], maxLat = ring[0][0], minLon = ring[0][1], maxLon = ring[0][1];
    for (const [lat, lon] of ring) {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
    }
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
 * Extract the outer polygon ring from a LocationEntry as [lat, lon][] pairs.
 * Falls back to a rectangle built from the bounding box if no polygon is stored.
 * Returns null when neither is available.
 */
export function getLocationRing(loc: LocationEntry): [number, number][] | null {
  if (loc.polygon) {
    const { type, coordinates } = loc.polygon;
    if (type === 'Polygon') {
      return (coordinates[0] as [number, number][]).map(([lon, lat]) => [lat, lon]);
    }
    if (type === 'MultiPolygon') {
      const rings = (coordinates as [number, number][][][]).map((p) => p[0]);
      const largest = rings.reduce((a, b) => (b.length > a.length ? b : a), rings[0] ?? []);
      return largest.map(([lon, lat]) => [lat, lon]);
    }
    // Lines have no area ring; use the bounding box of their coordinates (reliably
    // [lon, lat]) so a more-specific street can still suppress a containing area
    // polygon. Point geometries are skipped: stored point coordinates have an
    // unreliable lat/lon order, and the dot path already locates a node via the
    // dot's own (authoritative) lat/lon, so no ring is needed here.
    if (type === 'LineString' || type === 'MultiLineString') {
      const pts: [number, number][] =
        type === 'LineString'
          ? (coordinates as [number, number][])
          : (coordinates as [number, number][][]).flat();
      if (pts.length > 0) {
        let minLat = pts[0][1], maxLat = pts[0][1];
        let minLon = pts[0][0], maxLon = pts[0][0];
        for (const [lon, lat] of pts) {
          if (lat < minLat) minLat = lat;
          if (lat > maxLat) maxLat = lat;
          if (lon < minLon) minLon = lon;
          if (lon > maxLon) maxLon = lon;
        }
        return [[minLat, minLon], [minLat, maxLon], [maxLat, maxLon], [maxLat, minLon]];
      }
    }
  }
  if (Array.isArray(loc.boundingbox) && loc.boundingbox.length === 4) {
    const [minLat, maxLat, minLon, maxLon] = (loc.boundingbox as unknown[]).map(Number);
    return [[minLat, minLon], [minLat, maxLon], [maxLat, maxLon], [maxLat, minLon]];
  }
  return null;
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
    // Match the dot to its LocationEntry by lat/lon proximity (≈11 m tolerance).
    const loc = locs.find(
      (l) =>
        l.lat != null &&
        l.lon != null &&
        Math.abs(Number(l.lat) - d.lat) < 1e-4 &&
        Math.abs(Number(l.lon) - d.lon) < 1e-4,
    );
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
