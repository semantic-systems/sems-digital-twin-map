import React, { useEffect, useRef, useState } from 'react';
import { Polygon, Polyline, CircleMarker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { useFilterStore } from '../../store/useFilterStore';

const SNAP_PX = 14; // pixels from first vertex to auto-close the polygon
const COLOR = '#f59e0b'; // amber — distinct from the blue event polygons

// Outer ring covering the whole world — used as the mask shell
const WORLD: [number, number][] = [[-90, -180], [-90, 180], [90, 180], [90, -180]];

export function SpatialFilterLayer(): React.ReactElement {
  const map = useMap();
  const { spatialPolygon, spatialDrawMode, setSpatialPolygon } = useFilterStore();
  const [draft, setDraft] = useState<[number, number][]>([]);
  const clickTimerRef = useRef<number | null>(null);

  // Crosshair cursor while drawing
  useEffect(() => {
    map.getContainer().style.cursor = spatialDrawMode ? 'crosshair' : '';
    return () => { map.getContainer().style.cursor = ''; };
  }, [spatialDrawMode, map]);

  // Clear draft when draw mode is cancelled externally
  useEffect(() => {
    if (!spatialDrawMode) {
      if (clickTimerRef.current !== null) {
        window.clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      setDraft([]);
    }
  }, [spatialDrawMode]);

  const finalize = (points: [number, number][]) => {
    if (points.length >= 3) {
      setSpatialPolygon(points);
    }
    setDraft([]);
  };

  useMapEvents({
    click(e) {
      if (!spatialDrawMode) return;

      // Debounce to eat the first click of a double-click sequence
      if (clickTimerRef.current !== null) {
        window.clearTimeout(clickTimerRef.current);
      }
      const lat = e.latlng.lat;
      const lon = e.latlng.lng;
      clickTimerRef.current = window.setTimeout(() => {
        clickTimerRef.current = null;
        setDraft((prev) => {
          // Snap to first vertex to close
          if (prev.length >= 3) {
            const firstPx = map.latLngToContainerPoint(L.latLng(prev[0][0], prev[0][1]));
            const thisPx = map.latLngToContainerPoint(L.latLng(lat, lon));
            const dist = Math.hypot(thisPx.x - firstPx.x, thisPx.y - firstPx.y);
            if (dist <= SNAP_PX) {
              finalize(prev);
              return [];
            }
          }
          return [...prev, [lat, lon]];
        });
      }, 220);
    },

    dblclick() {
      if (!spatialDrawMode) return;
      // Cancel the pending single-click timer, then finalize current draft
      if (clickTimerRef.current !== null) {
        window.clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      setDraft((prev) => {
        finalize(prev);
        return [];
      });
    },
  });

  const canClose = draft.length >= 3;

  return (
    <>
      {/* Finalized polygon — border + dim mask outside */}
      {spatialPolygon && !spatialDrawMode && (
        <>
          {/* Dim everything outside the drawn area */}
          <Polygon
            positions={[WORLD, spatialPolygon]}
            pathOptions={{ stroke: false, fillColor: '#000', fillOpacity: 0.35, interactive: false }}
          />
          {/* Amber border so the selection edge is clearly visible */}
          <Polygon
            positions={spatialPolygon}
            pathOptions={{ color: COLOR, weight: 2, fill: false, interactive: false }}
          />
        </>
      )}

      {/* In-progress polygon outline */}
      {spatialDrawMode && draft.length >= 2 && (
        <Polyline
          positions={draft}
          pathOptions={{ color: COLOR, weight: 2, dashArray: '6 5', opacity: 0.9, interactive: false }}
        />
      )}

      {/* Preview closing edge */}
      {spatialDrawMode && canClose && (
        <Polyline
          positions={[draft[draft.length - 1], draft[0]]}
          pathOptions={{ color: COLOR, weight: 1.5, dashArray: '4 6', opacity: 0.4, interactive: false }}
        />
      )}

      {/* Vertex markers */}
      {spatialDrawMode && draft.map((pt, i) => (
        <CircleMarker
          key={i}
          center={pt}
          radius={i === 0 && canClose ? 7 : 4}
          pathOptions={{
            color: COLOR,
            fillColor: i === 0 && canClose ? COLOR : '#ffffff',
            fillOpacity: 1,
            weight: 2,
            interactive: false,
          }}
        />
      ))}
    </>
  );
}
