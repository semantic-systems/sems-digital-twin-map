import React, { useEffect, useRef, useState } from 'react';
import { useMap } from 'react-leaflet';
import { useReportStore } from '../../store/useReportStore';
import type { DotDTO } from '../../types';
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

/**
 * A single offscreen-navigation arrow. Every dot marker on the map has a native
 * Leaflet Popup, and Leaflet has its OWN built-in "close the popup when the user
 * clicks elsewhere on the map" behavior — completely separate from any of our
 * own React click handlers, and not something React's e.stopPropagation() can
 * prevent (React's synthetic dispatch and Leaflet's internal click detection
 * are two independent systems reacting to the same bubbling native event;
 * Leaflet's own container-level listener sees it first). The only thing that
 * actually stops a click here from being treated as "a click on the map" —
 * which would close whatever popup/detail overlay is open and immediately
 * deselect the active report — is Leaflet's own `L.DomEvent.disableClickPropagation`,
 * applied directly to this element's DOM node. Once that's in place, a plain
 * React onClick would never fire either (it also depends on the event bubbling
 * to the app root), so navigation is wired as a native listener on the same node.
 */
function ArrowMarker({ arrow, onNavigate }: { arrow: Arrow; onNavigate: (arrow: Arrow) => void }): React.ReactElement {
  const elRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    L.DomEvent.disableClickPropagation(el);
    const handleClick = () => onNavigate(arrow);
    el.addEventListener('click', handleClick);
    return () => el.removeEventListener('click', handleClick);
  }, [arrow, onNavigate]);

  return (
    <div
      ref={elRef}
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
  );
}

function ArrowsInner({ visibleDots }: { visibleDots: DotDTO[] }): React.ReactElement {
  const map = useMap();
  const { activeReportId } = useReportStore();
  const [arrows, setArrows] = useState<Arrow[]>([]);

  const computeArrows = () => {
    if (activeReportId === null) {
      setArrows([]);
      return;
    }

    // visibleDots is the SAME filtered/suppressed set ReportDots and
    // ActiveReportPolygons render from (seen/hidden respecting showHidden, the
    // drawn spatial filter, "only new", containment suppression) — arrows only
    // ever point at a dot that's actually shown on the map, and this can't drift
    // out of sync since it's one shared computation, not a re-implementation.
    const activeDots = visibleDots.filter((d) => d.report_id === activeReportId);

    const allPoints: { lat: number; lon: number; key: string }[] =
      activeDots.map((d, i) => ({ lat: d.lat, lon: d.lon, key: `dot-${i}` }));

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
  }, [activeReportId, visibleDots]);

  const handleNavigate = (arrow: Arrow) => {
    map.setView([arrow.lat, arrow.lon], Math.max(map.getZoom(), 14), { animate: false });
  };

  return (
    <>
      {arrows.map((arrow) => (
        <ArrowMarker key={arrow.key} arrow={arrow} onNavigate={handleNavigate} />
      ))}
    </>
  );
}

export function OffscreenArrows({ visibleDots }: { visibleDots: DotDTO[] }): React.ReactElement {
  return <ArrowsInner visibleDots={visibleDots} />;
}
