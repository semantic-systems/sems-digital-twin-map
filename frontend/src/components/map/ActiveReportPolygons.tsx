import React from 'react';
import { Polygon, Polyline, Rectangle } from 'react-leaflet';
import type { LatLngBoundsExpression, LatLngExpression } from 'leaflet';
import { useReportStore } from '../../store/useReportStore';
import type { LocationEntry, GeoJsonGeometry } from '../../types';

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

export function ActiveReportPolygons(): React.ReactElement {
  const { activeReportId, reports } = useReportStore();

  if (activeReportId === null) return <></>;

  const report = reports.find((r) => r.id === activeReportId);
  if (!report) return <></>;

  const effectiveLocs: LocationEntry[] =
    report.user_state.locations !== undefined && report.user_state.locations !== null
      ? report.user_state.locations
      : report.locations;

  const geoLocs = effectiveLocs.filter(isGeoLocation);

  // For locations with boundingbox but no polygon, also render rectangles
  const bbOnlyLocs = effectiveLocs.filter(
    (l) => l.osm_id && !l.polygon && l.boundingbox,
  );

  return (
    <>
      {geoLocs.map((loc, i) => (
        <LocationPolygon key={i} loc={loc} />
      ))}
      {bbOnlyLocs.map((loc, i) => {
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
