import React, { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import { useReportStore } from '../../store/useReportStore';
import type { LocationEntry } from '../../types';
import L from 'leaflet';

interface Arrow {
  key: string;
  x: number;
  y: number;
  bearing: number;
  lat: number;
  lon: number;
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
    const center = map.getCenter();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const sidebarWidth = 380;
    const filterBarHeight = 64;
    const arrowSize = 36;
    const margin = arrowSize / 2 + 4;

    const mapMinX = sidebarWidth + margin;
    const mapMaxX = vw - margin;
    const mapMinY = filterBarHeight + margin;
    const mapMaxY = vh - margin;

    const cx = (mapMinX + mapMaxX) / 2;
    const cy = (mapMinY + mapMaxY) / 2;

    const newArrows: Arrow[] = [];

    for (const pt of allPoints) {
      const ll = L.latLng(pt.lat, pt.lon);
      if (bounds.contains(ll)) continue;

      const bearing = computeBearing(center.lat, center.lng, pt.lat, pt.lon);
      const { x, y } = clampToViewport(cx, cy, bearing, mapMinX, mapMaxX, mapMinY, mapMaxY);

      newArrows.push({ key: pt.key, x, y, bearing, lat: pt.lat, lon: pt.lon });
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

  const handleArrowClick = (e: React.MouseEvent, arrow: Arrow) => {
    e.stopPropagation();
    map.setView([arrow.lat, arrow.lon], Math.max(map.getZoom(), 14), { animate: false });
  };

  return (
    <>
      {arrows.map((arrow) => (
        <div
          key={arrow.key}
          onClick={(e) => handleArrowClick(e, arrow)}
          title="Click to navigate"
          style={{
            position: 'fixed',
            left: arrow.x,
            top: arrow.y,
            transform: 'translate(-50%, -50%)',
            width: 36,
            height: 36,
            borderRadius: '50%',
            background: '#f97316',
            boxShadow: '0 2px 6px rgba(0,0,0,0.35)',
            pointerEvents: 'auto',
            cursor: 'pointer',
            zIndex: 490,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {/* Triangle pointing up, rotated to bearing */}
          <div
            style={{
              width: 0,
              height: 0,
              borderLeft: '7px solid transparent',
              borderRight: '7px solid transparent',
              borderBottom: '13px solid white',
              transform: `rotate(${arrow.bearing}deg)`,
              flexShrink: 0,
            }}
          />
        </div>
      ))}
    </>
  );
}

export function OffscreenArrows(): React.ReactElement {
  return <ArrowsInner />;
}
