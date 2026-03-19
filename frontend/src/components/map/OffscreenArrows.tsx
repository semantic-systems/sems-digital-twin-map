import React, { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import { useReportStore } from '../../store/useReportStore';
import type { LocationEntry } from '../../types';
import L from 'leaflet';

interface Arrow {
  key: string;
  x: number;
  y: number;
  direction: string; // 'N' | 'NE' | 'E' | 'SE' | 'S' | 'SW' | 'W' | 'NW'
  lat: number;
  lon: number;
}

function getDirection(bearingDeg: number): string {
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const idx = Math.round(((bearingDeg % 360) + 360) / 45) % 8;
  return dirs[idx];
}

function computeBearing(fromLat: number, fromLon: number, toLat: number, toLon: number): number {
  const dLon = ((toLon - fromLon) * Math.PI) / 180;
  const lat1 = (fromLat * Math.PI) / 180;
  const lat2 = (toLat * Math.PI) / 180;
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  return (Math.atan2(y, x) * 180) / Math.PI;
}

function clampToViewport(
  cx: number,
  cy: number,
  bearing: number,
  minX: number,
  maxX: number,
  minY: number,
  maxY: number,
): { x: number; y: number } {
  // Ray from map center toward target; clamp to map area edge
  const rad = (bearing * Math.PI) / 180;
  const dx = Math.sin(rad);
  const dy = -Math.cos(rad);

  let t = Infinity;
  if (dx > 0) t = Math.min(t, (maxX - cx) / dx);
  else if (dx < 0) t = Math.min(t, (minX - cx) / dx);
  if (dy > 0) t = Math.min(t, (maxY - cy) / dy);
  else if (dy < 0) t = Math.min(t, (minY - cy) / dy);

  return { x: cx + dx * t, y: cy + dy * t };
}

const DIRECTION_STYLES: Record<string, React.CSSProperties> = {
  N: { borderLeft: '8px solid transparent', borderRight: '8px solid transparent', borderBottom: '14px solid #f97316', transform: 'translate(-50%, -100%)' },
  NE: { borderLeft: '14px solid transparent', borderBottom: '14px solid #f97316', transform: 'translate(-20%, -80%)' },
  E: { borderTop: '8px solid transparent', borderBottom: '8px solid transparent', borderLeft: '14px solid #f97316', transform: 'translate(0, -50%)' },
  SE: { borderLeft: '14px solid transparent', borderTop: '14px solid #f97316', transform: 'translate(-20%, -20%)' },
  S: { borderLeft: '8px solid transparent', borderRight: '8px solid transparent', borderTop: '14px solid #f97316', transform: 'translate(-50%, 0)' },
  SW: { borderRight: '14px solid transparent', borderTop: '14px solid #f97316', transform: 'translate(-80%, -20%)' },
  W: { borderTop: '8px solid transparent', borderBottom: '8px solid transparent', borderRight: '14px solid #f97316', transform: 'translate(-100%, -50%)' },
  NW: { borderRight: '14px solid transparent', borderBottom: '14px solid #f97316', transform: 'translate(-80%, -80%)' },
};

function ArrowsInner(): React.ReactElement {
  const map = useMap();
  const { activeReportId, reports, dots } = useReportStore();
  const [arrows, setArrows] = useState<Arrow[]>([]);

  const computeArrows = () => {
    if (activeReportId === null) {
      setArrows([]);
      return;
    }

    const report = reports.find((r) => r.id === activeReportId);
    if (!report) {
      setArrows([]);
      return;
    }

    const effectiveLocs: LocationEntry[] =
      report.user_state.locations !== undefined && report.user_state.locations !== null
        ? report.user_state.locations
        : report.locations;

    const geoLocs = effectiveLocs.filter((l) => l.osm_id && l.lat && l.lon);

    // Also check dots
    const activeDots = dots.filter((d) => d.report_id === activeReportId);

    const allPoints: { lat: number; lon: number; key: string }[] = [
      ...geoLocs.map((l, i) => ({ lat: Number(l.lat), lon: Number(l.lon), key: `loc-${i}` })),
      ...activeDots.map((d, i) => ({ lat: d.lat, lon: d.lon, key: `dot-${i}` })),
    ];

    if (allPoints.length === 0) {
      setArrows([]);
      return;
    }

    const bounds = map.getBounds();
    const mapSize = map.getSize();
    const center = map.getCenter();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const sidebarWidth = 380;
    const filterBarHeight = 48;
    const margin = 20;

    // Map area bounds in fixed/window coords
    const mapMinX = sidebarWidth + margin;
    const mapMaxX = vw - margin;
    const mapMinY = filterBarHeight + margin;
    const mapMaxY = vh - margin;

    // Center of the map area
    const cx = (mapMinX + mapMaxX) / 2;
    const cy = (mapMinY + mapMaxY) / 2;

    const newArrows: Arrow[] = [];

    for (const pt of allPoints) {
      const ll = L.latLng(pt.lat, pt.lon);
      if (bounds.contains(ll)) continue;

      const bearing = computeBearing(center.lat, center.lng, pt.lat, pt.lon);
      const direction = getDirection(bearing);

      const { x, y } = clampToViewport(cx, cy, bearing, mapMinX, mapMaxX, mapMinY, mapMaxY);

      newArrows.push({ key: pt.key, x, y, direction, lat: pt.lat, lon: pt.lon });
    }

    setArrows(newArrows);
  };

  useEffect(() => {
    computeArrows();
    map.on('move zoom', computeArrows);
    return () => {
      map.off('move zoom', computeArrows);
    };
  }, [activeReportId, reports, dots]);

  const handleArrowClick = (arrow: Arrow) => {
    map.setView([arrow.lat, arrow.lon], Math.max(map.getZoom(), 14));
  };

  return (
    <>
      {arrows.map((arrow) => (
        <div
          key={arrow.key}
          onClick={() => handleArrowClick(arrow)}
          title="Click to navigate"
          style={{
            position: 'fixed',
            left: arrow.x,
            top: arrow.y,
            width: 0,
            height: 0,
            pointerEvents: 'auto',
            cursor: 'pointer',
            zIndex: 490,
            ...DIRECTION_STYLES[arrow.direction],
          }}
        />
      ))}
    </>
  );
}

export function OffscreenArrows(): React.ReactElement {
  return <ArrowsInner />;
}
