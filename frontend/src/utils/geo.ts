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

/**
 * For a group of dots belonging to the same report, returns dots that should be
 * hidden because another dot at a more specific location has its centroid inside
 * this dot's bounding box (meaning this dot's location is a spatial superset).
 *
 * Circular-suppression guard: when a's centroid is also inside b's bbox (mutual
 * containment — e.g. due to an inflated KG polygon) AND b's area is not smaller
 * than a's, we skip suppression for that pair rather than risk hiding both.
 */
export function computeSuppressedDots(groupDots: DotDTO[]): Set<DotDTO> {
  const suppressed = new Set<DotDTO>();
  for (let i = 0; i < groupDots.length; i++) {
    const a = groupDots[i];
    if (suppressed.has(a)) continue;
    const bb = a.location_bbox;
    if (!bb) continue;
    const [minLat, maxLat, minLon, maxLon] = bb;
    for (let j = 0; j < groupDots.length; j++) {
      if (i === j) continue;
      const b = groupDots[j];
      if (b.lat >= minLat && b.lat <= maxLat && b.lon >= minLon && b.lon <= maxLon) {
        // b's geocoded point is inside a's bbox → a is likely a spatial superset.
        // Only skip when there is genuine mutual containment (a's point also inside
        // b's bbox) AND b does not appear smaller — that combination signals that
        // b has an inflated/unreliable bbox and is NOT truly more specific than a.
        const bBb = b.location_bbox;
        if (bBb) {
          const aInBBox =
            a.lat >= bBb[0] && a.lat <= bBb[1] && a.lon >= bBb[2] && a.lon <= bBb[3];
          if (aInBBox) {
            const aArea = a.location_bbox_area;
            const bArea = b.location_bbox_area;
            if (aArea != null && bArea != null && bArea >= aArea) {
              continue; // mutual overlap, b not smaller → keep both
            }
          }
        }
        suppressed.add(a);
        break;
      }
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
    // Point / line geometries have no area ring; use the bounding box of their
    // coordinates so a more-specific node or street can still suppress a containing
    // area polygon. Mirrors getPrimaryRing() in ActiveReportPolygons so the dot and
    // polygon suppression paths agree on a feature's spatial extent.
    if (
      type === 'Point' ||
      type === 'MultiPoint' ||
      type === 'LineString' ||
      type === 'MultiLineString'
    ) {
      const pts: [number, number][] =
        type === 'Point'
          ? [coordinates as [number, number]]
          : type === 'MultiPoint' || type === 'LineString'
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
 * Like computeSuppressedDots, but uses the full LocationEntry polygon data
 * for containment checks — matching the same logic used by ActiveReportPolygons.
 * Pass the effective LocationEntry list for the report (user_state.locations ?? locations).
 */
export function computeSuppressedDotsWithLocs(
  groupDots: DotDTO[],
  locs: LocationEntry[],
): Set<DotDTO> {
  // Match each dot to its LocationEntry by lat/lon proximity (≈11 m tolerance).
  const dotLocs = groupDots.map((d) => ({
    dot: d,
    loc:
      locs.find(
        (l) =>
          l.lat != null &&
          l.lon != null &&
          Math.abs(Number(l.lat) - d.lat) < 1e-4 &&
          Math.abs(Number(l.lon) - d.lon) < 1e-4,
      ) ?? null,
  }));

  const suppressed = new Set<DotDTO>();

  for (let i = 0; i < dotLocs.length; i++) {
    const { dot: a, loc: locA } = dotLocs[i];
    if (suppressed.has(a)) continue;

    const ringA = locA ? getLocationRing(locA) : null;
    const bbA = a.location_bbox;

    for (let j = 0; j < dotLocs.length; j++) {
      if (i === j) continue;
      const { dot: b, loc: locB } = dotLocs[j];

      // Both dots resolved to the same LocationEntry (identical lat/lon within tolerance).
      // Comparing a loc against itself produces spurious mutual suppression — skip.
      if (locA !== null && locB === locA) continue;

      // Check if b's polygon is fully contained within a's region.
      // Using full bbox containment rather than a single-point check so that
      // partial overlap (e.g. Görlitzer Bahnbrücken polygon partly outside Berlin)
      // keeps both dots/polygons visible.
      let bInsideA = false;
      if (ringA && ringA.length >= 3) {
        // Derive B's spatial extent. Prefer dot.location_bbox (computed from the actual
        // polygon in location_polygons, which reflects the full geographic extent — e.g.
        // a rail route spanning two cities). Fall back to ring from loc.boundingbox, which
        // is only the Nominatim result's centroid bbox and may be much smaller.
        const ringB = locB ? getLocationRing(locB) : null;
        let bMinLat = b.lat, bMaxLat = b.lat, bMinLon = b.lon, bMaxLon = b.lon;
        let hasBbox = false;
        if (b.location_bbox) {
          [bMinLat, bMaxLat, bMinLon, bMaxLon] = b.location_bbox as number[];
          hasBbox = true;
        } else if (ringB && ringB.length > 0) {
          bMinLat = ringB[0][0]; bMaxLat = ringB[0][0];
          bMinLon = ringB[0][1]; bMaxLon = ringB[0][1];
          for (const [lat, lon] of ringB) {
            if (lat < bMinLat) bMinLat = lat;
            if (lat > bMaxLat) bMaxLat = lat;
            if (lon < bMinLon) bMinLon = lon;
            if (lon > bMaxLon) bMaxLon = lon;
          }
          hasBbox = true;
        }
        if (hasBbox) {
          bInsideA =
            pointInPolygon(bMinLat, bMinLon, ringA) &&
            pointInPolygon(bMinLat, bMaxLon, ringA) &&
            pointInPolygon(bMaxLat, bMinLon, ringA) &&
            pointInPolygon(bMaxLat, bMaxLon, ringA);
        } else {
          // No spatial extent available — fall back to geocoded point only
          bInsideA = pointInPolygon(b.lat, b.lon, ringA);
        }
      } else if (bbA) {
        const [minLat, maxLat, minLon, maxLon] = bbA;
        bInsideA = b.lat >= minLat && b.lat <= maxLat && b.lon >= minLon && b.lon <= maxLon;
      }
      if (!bInsideA) continue;

      // b is inside a → a is a spatial superset → suppress a, unless circular.
      // Circular guard: check if a's geocoded point is also inside b's region.
      const ringB = locB ? getLocationRing(locB) : null;
      const bbB = b.location_bbox;
      let aInsideB = false;
      if (ringB && ringB.length >= 3) {
        aInsideB = pointInPolygon(a.lat, a.lon, ringB);
      } else if (bbB) {
        const [minLat, maxLat, minLon, maxLon] = bbB;
        aInsideB = a.lat >= minLat && a.lat <= maxLat && a.lon >= minLon && a.lon <= maxLon;
      }

      if (aInsideB) {
        // Mutual containment — use area to break the tie (same as computeSuppressed).
        const aArea = locA ? locationBboxArea(locA) : a.location_bbox_area;
        const bArea = locB ? locationBboxArea(locB) : b.location_bbox_area;
        if (aArea != null && bArea != null && bArea > aArea) {
          continue; // b appears larger → don't suppress a
        }
      }

      suppressed.add(a);
      break;
    }
  }

  return suppressed;
}

/**
 * Bounding-box area in degrees² from a LocationEntry. Returns null if no geometry
 * is available. Derived from getLocationRing so every geometry type (polygon, line,
 * point, bbox) is handled identically to the containment checks — a point yields 0.
 */
export function locationBboxArea(loc: LocationEntry): number | null {
  const ring = getLocationRing(loc);
  return ring ? polygonBboxArea(ring) : null;
}
