import React, { useEffect, useState } from 'react';
import { Polygon, Polyline, Rectangle } from 'react-leaflet';
import type { LatLngBoundsExpression, LatLngExpression } from 'leaflet';
import { useReportStore } from '../../store/useReportStore';
import { fetchReport } from '../../api/reports';
import type { LocationEntry, GeoJsonGeometry, ReportDTO, DotDTO } from '../../types';
import { computeSuppressedRegions, locationExtent, filterLocationsWithVisibleDots, dedupByOsm, osmKey } from '../../utils/geo';

function coordsToLatLng(coords: unknown[]): LatLngExpression[] {
  return (coords as [number, number][]).map(([lon, lat]) => [lat, lon]);
}

function polygonCoordsToLatLng(coords: unknown[]): LatLngExpression[][] {
  return (coords as unknown[][]).map((ring) =>
    (ring as [number, number][]).map(([lon, lat]) => [lat, lon]),
  );
}

interface GeoLocation extends LocationEntry {
  polygon: GeoJsonGeometry;
  osm_id: string;
}

function isGeoLocation(loc: LocationEntry): loc is GeoLocation {
  return Boolean(loc.osm_id && loc.polygon);
}

/**
 * Fills in polygon geometry from the lazily-fetched detail report, WITHOUT
 * treating detail as the authoritative location list. `rawLocs` (always derived
 * from the live `reports` store) already reflects any in-progress edit the
 * moment it's made; `detail` only ever gets refreshed when activeReportId/
 * username changes, so it can be stale relative to an edit on the report
 * that's already active. Previously `detail.locations` was used outright when
 * present, which showed pre-edit locations until the report was deselected and
 * reselected. Matching by normalized OSM entity (not array position) means a
 * freshly-picked location's own polygon (PickModeOverlay attaches one directly
 * from the Nominatim result) is never overwritten, and other locations still
 * get their polygon filled in from the cached detail fetch once it's loaded.
 */
function mergeDetailPolygons(
  rawLocs: LocationEntry[],
  detail: ReportDTO | null,
  activeReportId: number,
): LocationEntry[] {
  if (!detail || detail.id !== activeReportId) return rawLocs;
  const polyByKey = new Map<string, GeoJsonGeometry>();
  for (const l of detail.locations) {
    if (l.polygon && l.osm_id) polyByKey.set(osmKey(l), l.polygon);
  }
  return rawLocs.map((l) => {
    if (l.polygon || !l.osm_id) return l;
    const poly = polyByKey.get(osmKey(l));
    return poly ? { ...l, polygon: poly } : l;
  });
}

function LocationPolygon({ loc }: { loc: GeoLocation }): React.ReactElement | null {
  const geo = loc.polygon;

  if (geo.type === 'Polygon') {
    const positions = polygonCoordsToLatLng(geo.coordinates);
    return (
      <Polygon
        positions={positions as LatLngExpression[][]}
        pathOptions={{
          color: '#3b82f6',
          fillColor: '#3b82f6',
          fillOpacity: 0.15,
          weight: 2,
        }}
      />
    );
  }

  if (geo.type === 'MultiPolygon') {
    const allPolygons = (geo.coordinates as unknown[][][]).map((poly) =>
      polygonCoordsToLatLng(poly),
    );
    return (
      <>
        {allPolygons.map((positions, i) => (
          <Polygon
            key={i}
            positions={positions as LatLngExpression[][]}
            pathOptions={{
              color: '#3b82f6',
              fillColor: '#3b82f6',
              fillOpacity: 0.15,
              weight: 2,
            }}
          />
        ))}
      </>
    );
  }

  if (geo.type === 'LineString') {
    const positions = coordsToLatLng(geo.coordinates);
    return (
      <Polyline
        positions={positions}
        pathOptions={{ color: '#1d4ed8', weight: 3 }}
      />
    );
  }

  if (geo.type === 'MultiLineString') {
    return (
      <>
        {(geo.coordinates as unknown[][]).map((line, i) => (
          <Polyline
            key={i}
            positions={coordsToLatLng(line)}
            pathOptions={{ color: '#1d4ed8', weight: 3 }}
          />
        ))}
      </>
    );
  }

  // Fallback: bounding box
  if (loc.boundingbox) {
    const bb = loc.boundingbox;
    const bounds: LatLngBoundsExpression = [
      [Number(bb[0]), Number(bb[2])],
      [Number(bb[1]), Number(bb[3])],
    ];
    return (
      <Rectangle
        bounds={bounds}
        pathOptions={{
          color: '#3b82f6',
          fillColor: '#3b82f6',
          fillOpacity: 0.1,
          weight: 2,
          dashArray: '4 4',
        }}
      />
    );
  }

  return null;
}

export function ActiveReportPolygons({ visibleDots }: { visibleDots: DotDTO[] }): React.ReactElement {
  const { activeReportId, reports } = useReportStore();
  const [detailReport, setDetailReport] = useState<ReportDTO | null>(null);

  useEffect(() => {
    if (activeReportId === null) { setDetailReport(null); return; }
    let cancelled = false;
    // fetchReport goes through apiFetch (sends the session cookie; the user is
    // derived server-side — no client username param anymore).
    fetchReport(activeReportId)
      .then((data) => { if (!cancelled) setDetailReport(data); })
      .catch(() => { if (!cancelled) setDetailReport(null); });
    // Guard against out-of-order responses when the active report changes
    // quickly: a stale fetch must not overwrite the current detail report.
    return () => { cancelled = true; };
  }, [activeReportId]);

  if (activeReportId === null) return <></>;

  // Polygon geometry is only attached by the single-report detail endpoint
  // (the list endpoint, and therefore report.locations / user_state.locations,
  // never carry a polygon). The detail report is fetched independently of the
  // sidebar list, so it exists even when the active report falls outside the
  // list's current pagination/filters (e.g. selected via a map dot).
  const detail =
    detailReport && detailReport.id === activeReportId ? detailReport : null;
  // `active` always comes from the live `reports` store when the report is
  // loaded there — NOT from `detail` — so it reflects an in-progress location
  // edit immediately. Falling back to `detail` only covers a report selected
  // via a map dot that fell outside the list's current page.
  const active = reports.find((r) => r.id === activeReportId) ?? detail ?? null;
  if (!active) return <></>;

  // The location list itself is always the live one; `detail` (once loaded)
  // only contributes polygon geometry for locations that don't already carry
  // their own (see mergeDetailPolygons).
  const rawLocs: LocationEntry[] = mergeDetailPolygons(
    active.user_state.locations ?? active.locations,
    detail,
    activeReportId,
  );

  // A polygon may only exist for a location that has a currently-visible dot —
  // this is what binds the two together. It replaces the old standalone
  // `active.user_state.hide` check and additionally makes polygons respect
  // showHidden/the drawn spatial filter/"only new" the same way dots do, since
  // those are exactly the filters useVisibleDots already applies.
  const effectiveLocs = filterLocationsWithVisibleDots(rawLocs, activeReportId, visibleDots);

  const geoLocs = effectiveLocs.filter(isGeoLocation);

  // For locations with boundingbox but no polygon, also render rectangles
  const bbOnlyLocs = effectiveLocs.filter(
    (l) => l.osm_id && !l.polygon && l.boundingbox,
  );

  // Hide locations that are supersets of another location in the same report, using
  // the exact same bbox-based decision as the map dots (computeSuppressedRegions).
  // Computed over ALL effective locations — not just the renderable polygon/bbox ones —
  // so a precise point that renders nothing can still suppress a containing polygon,
  // matching how its dot suppresses the area dot.
  const suppressedIdx = computeSuppressedRegions(effectiveLocs.map((l) => locationExtent(l)));
  const suppressed = new Set<LocationEntry>();
  suppressedIdx.forEach((i) => suppressed.add(effectiveLocs[i]));
  const visibleGeoLocs = dedupByOsm(geoLocs.filter((l) => !suppressed.has(l)));
  const visibleBbLocs = dedupByOsm(bbOnlyLocs.filter((l) => !suppressed.has(l)));

  return (
    <>
      {visibleGeoLocs.map((loc, i) => (
        <LocationPolygon key={i} loc={loc} />
      ))}
      {visibleBbLocs.map((loc, i) => {
        const bb = loc.boundingbox!;
        const bounds: LatLngBoundsExpression = [
          [Number(bb[0]), Number(bb[2])],
          [Number(bb[1]), Number(bb[3])],
        ];
        return (
          <Rectangle
            key={`bb-${i}`}
            bounds={bounds}
            pathOptions={{
              color: '#3b82f6',
              fillColor: '#3b82f6',
              fillOpacity: 0.1,
              weight: 2,
              dashArray: '4 4',
            }}
          />
        );
      })}
    </>
  );
}
