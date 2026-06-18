import React from 'react';
import { Polygon, Polyline, Rectangle } from 'react-leaflet';
import type { LatLngBoundsExpression, LatLngExpression } from 'leaflet';
import { useReportStore } from '../../store/useReportStore';
import type { LocationEntry, GeoJsonGeometry } from '../../types';
import { pointInPolygon, polygonBboxArea } from '../../utils/geo';

function coordsToLatLng(coords: unknown[]): LatLngExpression[] {
  return (coords as [number, number][]).map(([lon, lat]) => [lat, lon]);
}

function polygonCoordsToLatLng(coords: unknown[]): LatLngExpression[][] {
  return (coords as unknown[][]).map((ring) =>
    (ring as [number, number][]).map(([lon, lat]) => [lat, lon]),
  );
}

/** Extract the largest ring from a location as [lat, lon][], or build one from its boundingbox. */
function getPrimaryRing(loc: LocationEntry): [number, number][] | null {
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
  }
  if (loc.boundingbox && loc.boundingbox.length === 4) {
    const [minLat, maxLat, minLon, maxLon] = (loc.boundingbox as unknown[]).map(Number);
    return [[minLat, minLon], [minLat, maxLon], [maxLat, maxLon], [maxLat, minLon]];
  }
  return null;
}

/** Bounding-box centre of a [lat, lon][] ring. */
function ringCenter(ring: [number, number][]): [number, number] {
  let minLat = ring[0][0], maxLat = ring[0][0];
  let minLon = ring[0][1], maxLon = ring[0][1];
  for (const [lat, lon] of ring) {
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
  }
  return [(minLat + maxLat) / 2, (minLon + maxLon) / 2];
}

/**
 * Returns the subset of locs that should be hidden because a more-specific
 * sibling location's centre falls inside their polygon (i.e. they are a
 * superset of another location in the same report).
 */
function computeSuppressed(locs: LocationEntry[]): Set<LocationEntry> {
  const items = locs.map((loc) => {
    const ring = getPrimaryRing(loc);
    return ring && ring.length >= 3 ? { loc, ring, center: ringCenter(ring) } : null;
  });

  const suppressed = new Set<LocationEntry>();
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (!item || suppressed.has(item.loc)) continue;
    for (let j = 0; j < items.length; j++) {
      if (i === j) continue;
      const other = items[j];
      if (!other) continue;
      if (pointInPolygon(other.center[0], other.center[1], item.ring)) {
        // Only suppress if the other location is strictly more specific (smaller area).
        const itemArea = polygonBboxArea(item.ring);
        const otherArea = polygonBboxArea(other.ring);
        if (otherArea <= itemArea) {
          suppressed.add(item.loc);
          break;
        }
      }
    }
  }
  return suppressed;
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

export function ActiveReportPolygons(): React.ReactElement {
  const { activeReportId, reports } = useReportStore();

  if (activeReportId === null) return <></>;

  const report = reports.find((r) => r.id === activeReportId);
  if (!report || report.user_state.hide) return <></>;

  const effectiveLocs: LocationEntry[] =
    report.user_state.locations !== undefined && report.user_state.locations !== null
      ? report.user_state.locations
      : report.locations;

  const geoLocs = effectiveLocs.filter(isGeoLocation);

  // For locations with boundingbox but no polygon, also render rectangles
  const bbOnlyLocs = effectiveLocs.filter(
    (l) => l.osm_id && !l.polygon && l.boundingbox,
  );

  // Hide locations that are supersets of another location in the same report.
  const suppressed = computeSuppressed([...geoLocs, ...bbOnlyLocs]);
  const visibleGeoLocs = geoLocs.filter((l) => !suppressed.has(l));
  const visibleBbLocs = bbOnlyLocs.filter((l) => !suppressed.has(l));

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
