import React, { useEffect, useState } from 'react';
import { Polygon, Polyline, Rectangle } from 'react-leaflet';
import type { LatLngBoundsExpression, LatLngExpression } from 'leaflet';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import type { LocationEntry, GeoJsonGeometry, ReportDTO, DotDTO } from '../../types';
import { computeSuppressedRegions, locationExtent, filterLocationsWithVisibleDots, dedupByOsm } from '../../utils/geo';

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
  const username = useUserStore((s) => s.username);
  const [detailReport, setDetailReport] = useState<ReportDTO | null>(null);

  useEffect(() => {
    if (activeReportId === null) { setDetailReport(null); return; }
    let cancelled = false;
    const qs = username ? `?username=${encodeURIComponent(username)}` : '';
    fetch(`/api/v1/reports/${activeReportId}${qs}`)
      .then((r) => r.json())
      .then((data: ReportDTO) => { if (!cancelled) setDetailReport(data); })
      .catch(() => { if (!cancelled) setDetailReport(null); });
    // Guard against out-of-order responses when the active report changes
    // quickly: a stale fetch must not overwrite the current detail report.
    return () => { cancelled = true; };
  }, [activeReportId, username]);

  if (activeReportId === null) return <></>;

  // Polygon geometry is only attached by the single-report detail endpoint
  // (the list endpoint, and therefore report.locations / user_state.locations,
  // never carry a polygon). The detail report is also fetched independently of
  // the sidebar list, so it exists even when the active report falls outside the
  // list's current pagination/filters (e.g. selected via a map dot) — relying on
  // it here is what lets those polygons render at all. While the fetch is in
  // flight, fall back to the in-list report (no polygon data yet, so nothing
  // draws until the detail arrives).
  const detail =
    detailReport && detailReport.id === activeReportId ? detailReport : null;
  const active = detail ?? reports.find((r) => r.id === activeReportId) ?? null;
  if (!active) return <></>;

  // detail.locations already reflects any user-modified locations AND polygon
  // enrichment, so trust it directly; only consult user_state.locations during
  // the loading fallback (it is unenriched, so renders nothing until detail loads).
  const rawLocs: LocationEntry[] = detail
    ? detail.locations
    : (active.user_state.locations ?? active.locations);

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
