import React, { useMemo, useRef, useEffect, useCallback, useState } from 'react';
import ReactDOM from 'react-dom';
import { Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { useReportStore } from '../../store/useReportStore';
import { useFilterStore } from '../../store/useFilterStore';
import { useUserStore } from '../../store/useUserStore';
import { hideReport, flagReport, acknowledgeReport } from '../../api/reports';
import { t } from '../../i18n';
import type { DotDTO, ReportDTO } from '../../types';
import { pointInPolygon, polygonBboxArea, computeSuppressedDotsWithLocs } from '../../utils/geo';

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

const RELEVANCE_COLORS: Record<string, string> = {
  high: '#b91c1c',
  medium: '#ea580c',
  low: '#ca8a04',
  none: '#6b7280',
};

const RELEVANCE_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2, none: 3 };

// ---------------------------------------------------------------------------
// Grouping
// ---------------------------------------------------------------------------

interface DotGroup {
  lat: number;
  lon: number;
  dots: DotDTO[];
}

function clusterDots(dots: DotDTO[], leafletMap: L.Map, cellSize = 60): DotGroup[] {
  const cellMap = new Map<string, DotDTO[]>();
  for (const dot of dots) {
    const px = leafletMap.latLngToContainerPoint([dot.lat, dot.lon]);
    const key = `${Math.floor(px.x / cellSize)},${Math.floor(px.y / cellSize)}`;
    if (!cellMap.has(key)) cellMap.set(key, []);
    cellMap.get(key)!.push(dot);
  }
  return Array.from(cellMap.values()).map((group) => {
    const lat = group.reduce((s, d) => s + d.lat, 0) / group.length;
    const lon = group.reduce((s, d) => s + d.lon, 0) / group.length;
    return { lat, lon, dots: group };
  });
}

// ---------------------------------------------------------------------------
// DivIcon factory
// ---------------------------------------------------------------------------

function makeDotIcon({
  color, size, count, hasNew, isActive,
}: {
  color: string; size: number; count: number; hasNew: boolean; isActive: boolean;
}): L.DivIcon {
  const borderWidth = isActive ? 3 : 2;
  const countBadge = count > 1
    ? `<div style="position:absolute;top:-8px;right:-8px;background:#1f2937;color:#fff;font-size:9px;font-weight:700;font-family:'Inter',sans-serif;border-radius:999px;padding:1px 5px;min-width:16px;text-align:center;line-height:1.5;border:1.5px solid #fff;pointer-events:none;">${count}</div>`
    : '';
  const exclamation = hasNew && !isActive
    ? `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;font-size:${Math.round(size * 0.55)}px;font-weight:900;color:#fff;font-family:'Inter',sans-serif;line-height:1;text-shadow:0 1px 2px rgba(0,0,0,0.4);">!</div>`
    : '';
  return L.divIcon({
    html: `<div style="position:relative;width:${size}px;height:${size}px;">
      <div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:${borderWidth}px solid #ffffff;box-sizing:border-box;box-shadow:0 1px 4px rgba(0,0,0,0.45);"></div>
      ${exclamation}
      ${countBadge}
    </div>`,
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -(size / 2 + 6)],
  });
}

// ---------------------------------------------------------------------------
// DotPopup (used both inside Leaflet Popup and inside detail overlay)
// ---------------------------------------------------------------------------

function DotPopup({ dot }: { dot: DotDTO }): React.ReactElement {
  const { username } = useUserStore();
  const { optimisticHide, optimisticFlag, reports } = useReportStore();
  const report = reports.find((r) => r.id === dot.report_id);

  const handleHide = async () => {
    if (!username || !report) return;
    const newHide = !report.user_state.hide;
    optimisticHide(dot.report_id, newHide);
    try { await hideReport(dot.report_id, username, newHide); }
    catch (e) { console.error('Failed to hide:', e); }
  };

  const handleFlag = async () => {
    if (!username || !dot.author || !report) return;
    const newFlag = !report.user_state.flag;
    optimisticFlag(dot.author, newFlag);
    try { await flagReport(dot.report_id, username, newFlag); }
    catch (e) { console.error('Failed to flag:', e); }
  };

  const btn: React.CSSProperties = {
    fontSize: 11, padding: '2px 8px', borderRadius: 4,
    border: '1px solid #d1d5db', background: '#f3f4f6', color: '#374151',
    cursor: 'pointer', fontFamily: "'Inter', system-ui, sans-serif",
  };

  return (
    <div style={{ maxWidth: 260, fontFamily: "'Inter', system-ui, sans-serif" }}>
      {dot.new && (
        <span style={{
          display: 'inline-block', background: '#ef4444', color: '#fff',
          fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 999,
          marginBottom: 4, letterSpacing: '0.05em',
        }}>
          {t('new_badge')}
        </span>
      )}
      <p style={{ fontSize: 12, color: '#1f2937', marginBottom: 6, lineHeight: 1.4 }}>
        {dot.text.slice(0, 200)}{dot.text.length > 200 ? '…' : ''}
      </p>
      <p style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>
        {dot.author ? `@${dot.author} · ` : ''}{dot.platform}
      </p>
      {(dot.location_display || dot.location_name) && (() => {
        const isCoord = (s: string) => /^-?\d+\.\d+,\s*-?\d+\.\d+$/.test(s.trim());
        const showName = dot.location_name &&
          dot.location_name !== dot.location_display &&
          !isCoord(dot.location_name);
        return (
          <p style={{ fontSize: 11, color: '#374151', marginBottom: 2, fontWeight: 500 }}>
            📍 {dot.location_display || dot.location_name}
            {dot.location_display && showName && (
              <span style={{ fontWeight: 400, color: '#6b7280' }}> · {dot.location_name}</span>
            )}
          </p>
        );
      })()}
      <p style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
        {(dot.event_types ?? []).join(', ')} · {formatTimestamp(dot.timestamp)}
      </p>
      <div style={{ display: 'flex', gap: 4 }}>
        <a href={dot.url} target="_blank" rel="noopener noreferrer"
          style={{ ...btn, textDecoration: 'none', display: 'inline-block' }}>
          {t('open')}
        </a>
        {report && (
          <>
            <button onClick={handleHide} style={btn}>
              {report.user_state.hide ? t('unhide') : t('hide')}
            </button>
            {dot.author && (
              <button onClick={handleFlag} style={btn}>
                {report.user_state.flag ? t('unflag') : t('flag')}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Multi-dot aggregate popup (list only — no embedded detail view)
// ---------------------------------------------------------------------------

function MultiDotPopup({ dots, onSelect }: {
  dots: DotDTO[];
  onSelect: (dot: DotDTO) => void;
}): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) L.DomEvent.disableClickPropagation(containerRef.current);
  }, []);

  const rowStyle: React.CSSProperties = {
    cursor: 'pointer', borderRadius: 4, padding: '4px 6px',
    borderBottom: '1px solid #f3f4f6',
  };

  return (
    <div ref={containerRef} style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ maxWidth: 300 }}>
        <p style={{
          fontSize: 11, fontWeight: 700, color: '#374151',
          marginBottom: 8, borderBottom: '1px solid #e5e7eb', paddingBottom: 4,
        }}>
          {dots.length} Ereignisse an diesem Ort
        </p>
        <div style={{ maxHeight: 300, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {dots.map((dot) => (
            <div
              key={dot.report_id}
              style={rowStyle}
              onClick={() => onSelect(dot)}
              onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#f9fafb'; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = ''; }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 5, marginBottom: 2 }}>
                {dot.new && (
                  <span style={{
                    background: '#ef4444', color: '#fff', fontSize: 8, fontWeight: 700,
                    padding: '1px 4px', borderRadius: 999, whiteSpace: 'nowrap', flexShrink: 0,
                  }}>
                    NEU
                  </span>
                )}
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 2,
                  background: RELEVANCE_COLORS[dot.relevance] ?? '#6b7280',
                  border: '1px solid rgba(0,0,0,0.15)', display: 'inline-block',
                }} />
                <p style={{ fontSize: 11, color: '#1f2937', lineHeight: 1.35, margin: 0 }}>
                  {dot.text.slice(0, 80)}{dot.text.length > 80 ? '…' : ''}
                </p>
              </div>
              <span style={{ fontSize: 10, color: '#6b7280', paddingLeft: 13 }}>
                {dot.author ? `@${dot.author} · ` : ''}{dot.platform} · {(dot.event_types ?? []).join(', ')} · {formatTimestamp(dot.timestamp)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail overlay — React portal, completely outside Leaflet popup system
// ---------------------------------------------------------------------------

function DetailOverlay({
  dot, pos, onClose, onBack,
}: {
  dot: DotDTO;
  pos: { x: number; y: number };
  onClose: () => void;
  onBack: () => void;
}): React.ReactElement | null {
  if (!dot) return null;

  const headerBtn: React.CSSProperties = {
    background: 'none', border: 'none', cursor: 'pointer',
    color: '#6b7280', fontSize: 11, lineHeight: 1, padding: '0',
    fontFamily: "'Inter', system-ui, sans-serif",
  };

  return ReactDOM.createPortal(
    <div
      style={{
        position: 'fixed',
        left: pos.x,
        top: pos.y - 18,
        transform: 'translateX(-50%) translateY(-100%)',
        background: '#fff',
        borderRadius: 8,
        boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
        padding: '8px 12px 12px',
        zIndex: 1000,
        minWidth: 220,
        maxWidth: 280,
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, borderBottom: '1px solid #f3f4f6', paddingBottom: 6 }}>
        <button onClick={onBack} style={headerBtn} title="Back to list">
          ← Zurück zur Liste
        </button>
        <button onClick={onClose} style={{ ...headerBtn, fontSize: 14, color: '#9ca3af' }} title="Close">
          ✕
        </button>
      </div>
      <DotPopup dot={dot} />
    </div>,
    document.body,
  );
}

// ---------------------------------------------------------------------------
// GroupMarker — stable event handlers via mutable-ref pattern
// ---------------------------------------------------------------------------

interface GroupMarkerProps {
  group: DotGroup;
  groupKey: string;
  activeReportId: number | null;
  activeGroupKeyRef: React.MutableRefObject<string | null>;
  username: string | null;
  map: L.Map;
  didSelectRef: React.MutableRefObject<boolean>;
  dotClickRef: React.MutableRefObject<boolean>;
  reports: ReportDTO[];
  setActiveReportId: (id: number | null) => void;
  optimisticAcknowledge: (id: number) => void;
  openDetail: (dot: DotDTO, lat: number, lon: number, reopenPopup: () => void) => void;
  closeDetail: () => void;
}

const GroupMarker = React.memo(function GroupMarker({
  group, groupKey, activeReportId, activeGroupKeyRef, username, map,
  didSelectRef, dotClickRef,
  reports, setActiveReportId, optimisticAcknowledge,
  openDetail, closeDetail,
}: GroupMarkerProps) {
  const isGroupActive = group.dots.some((d) => d.report_id === activeReportId);
  const hasNew = group.dots.some((d) => d.new);

  // Deduplicate by report_id — multiple locations from one event count as one.
  const dedupedDots = useMemo(() => {
    const byReport = new Map<number, DotDTO>();
    for (const d of group.dots) {
      const existing = byReport.get(d.report_id);
      if (!existing || (RELEVANCE_ORDER[d.relevance] ?? 3) < (RELEVANCE_ORDER[existing.relevance] ?? 3)) {
        byReport.set(d.report_id, d);
      }
    }
    return [...byReport.values()].sort(
      (a, b) => (RELEVANCE_ORDER[a.relevance] ?? 3) - (RELEVANCE_ORDER[b.relevance] ?? 3),
    );
  }, [group.dots]);

  const isMulti = dedupedDots.length > 1;

  const primaryDot = dedupedDots[0];

  const color = isGroupActive ? '#3b82f6' : (RELEVANCE_COLORS[primaryDot.relevance] ?? '#6b7280');
  const size = isGroupActive ? 26 : isMulti ? 24 : 20;

  const icon = useMemo(
    () => makeDotIcon({ color, size, count: dedupedDots.length, hasNew, isActive: isGroupActive }),
    [color, size, dedupedDots.length, hasNew, isGroupActive],
  );

  // Ref to the Leaflet Marker instance so we can reopen the popup programmatically.
  const markerRef = useRef<L.Marker>(null);

  // Mutable ref so stable closures always see latest values.
  const s = useRef({
    isMulti, group, dedupedDots, groupKey, activeReportId, activeGroupKeyRef, username, reports,
    setActiveReportId, optimisticAcknowledge,
    didSelectRef, dotClickRef, map,
    openDetail, closeDetail, markerRef,
  });
  s.current = {
    isMulti, group, dedupedDots, groupKey, activeReportId, activeGroupKeyRef, username, reports,
    setActiveReportId, optimisticAcknowledge,
    didSelectRef, dotClickRef, map,
    openDetail, closeDetail, markerRef,
  };

  // Identity-stable event handlers — useEventHandlers never removes/re-adds them.
  const eventHandlers = useMemo(() => ({
    click: () => {
      const { isMulti, dedupedDots, groupKey, activeReportId, activeGroupKeyRef, username, dotClickRef, setActiveReportId, optimisticAcknowledge } = s.current;
      if (!isMulti) {
        const dot = dedupedDots[0];
        // Only deactivate when clicking the exact same marker that's already active.
        // A different dot of the same report (different position) keeps the report active.
        const isSameMarker = dot.report_id === activeReportId && activeGroupKeyRef.current === groupKey;
        const newId = isSameMarker ? null : dot.report_id;
        activeGroupKeyRef.current = newId !== null ? groupKey : null;
        dotClickRef.current = true;
        setActiveReportId(newId);
        if (newId !== null && username && dot.new) {
          optimisticAcknowledge(newId);
          acknowledgeReport(newId, username).catch(() => {});
        }
      }
    },
    popupopen: () => {
      const { isMulti, didSelectRef, closeDetail } = s.current;
      if (isMulti) {
        closeDetail();
        didSelectRef.current = false;
      }
    },
    popupclose: () => {
      const { didSelectRef, setActiveReportId } = s.current;
      if (!didSelectRef.current) setActiveReportId(null);
      didSelectRef.current = false;
    },
  }), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Stable onSelect: closes the Leaflet popup FIRST, then triggers store updates.
  const onSelect = useCallback((dot: DotDTO) => {
    const { didSelectRef, dotClickRef, map, setActiveReportId, username, optimisticAcknowledge, group, openDetail } = s.current;
    didSelectRef.current = true;
    dotClickRef.current = true;
    map.closePopup(); // close aggregate popup before any re-renders
    setActiveReportId(dot.report_id);
    if (dot.new && username) {
      optimisticAcknowledge(dot.report_id);
      acknowledgeReport(dot.report_id, username).catch(() => {});
    }
    // Pass a reopen function so the detail overlay's back button can reopen this popup.
    const reopenPopup = () => {
      s.current.didSelectRef.current = false;
      s.current.markerRef.current?.openPopup();
    };
    openDetail(dot, group.lat, group.lon, reopenPopup);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Marker ref={markerRef} position={[group.lat, group.lon]} icon={icon} eventHandlers={eventHandlers}>
      {/* autoPan disabled: an open popup must never pull the map view towards
          itself when the user pans or zooms. */}
      <Popup autoPan={false}>
        {isMulti
          ? <MultiDotPopup dots={dedupedDots} onSelect={onSelect} />
          : <DotPopup dot={dedupedDots[0]} />}
      </Popup>
    </Marker>
  );
});

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ReportDots(): React.ReactElement {
  const map = useMap();
  const { dots, activeReportId, setActiveReportId, optimisticAcknowledge, reports } = useReportStore();
  const { username } = useUserStore();
  const { showHidden, spatialPolygon } = useFilterStore();

  const [zoom, setZoom] = useState(() => map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });

  const visibleDots = useMemo(() => {
    const hiddenIds = showHidden
      ? new Set<number>()
      : new Set(reports.filter((r) => r.user_state.hide).map((r) => r.id));
    let result = showHidden
      ? dots
      : dots.filter((d) => !d.seen && !hiddenIds.has(d.report_id));
    if (spatialPolygon) {
      result = result.filter((d) => pointInPolygon(d.lat, d.lon, spatialPolygon));

      // Drop dots whose location granularity is as large as or larger than the drawn area.
      // E.g. a "Germany" geocode dot is confusing inside a Germany-sized spatial filter.
      const filterArea = polygonBboxArea(spatialPolygon);
      if (filterArea > 0) {
        result = result.filter((d) => {
          const locArea = d.location_bbox_area;
          // No area info → keep (precise pin-drop or unknown)
          if (locArea == null) return true;
          // Strict less-than: hide when the location is the same scale as (or larger than) the filter
          return locArea < filterArea;
        });
      }
    }
    // Containment suppression: for each report, hide dots whose location polygon
    // contains another dot of the same report (i.e. they are a spatial superset).
    const byReport = new Map<number, typeof result>();
    for (const d of result) {
      if (!byReport.has(d.report_id)) byReport.set(d.report_id, []);
      byReport.get(d.report_id)!.push(d);
    }
    const suppressed = new Set<(typeof result)[0]>();
    for (const [reportId, group] of byReport.entries()) {
      if (group.length > 1) {
        const report = reports.find((r) => r.id === reportId);
        const locs = report ? (report.user_state.locations ?? report.locations ?? []) : [];
        for (const d of computeSuppressedDotsWithLocs(group, locs)) suppressed.add(d);
      }
    }
    return result.filter((d) => !suppressed.has(d));
  }, [dots, showHidden, reports, spatialPolygon]);

  const groups = useMemo(() => clusterDots(visibleDots, map), [visibleDots, zoom]); // eslint-disable-line react-hooks/exhaustive-deps
  const didSelectRef = useRef(false);
  const dotClickRef = useRef(false);
  const activeGroupKeyRef = useRef<string | null>(null);

  // Detail overlay state — separate from Leaflet popup system entirely.
  const [detailState, setDetailState] = useState<{
    dot: DotDTO; lat: number; lon: number; reopenPopup: () => void;
  } | null>(null);
  const [detailPos, setDetailPos] = useState<{ x: number; y: number } | null>(null);

  // Close any open Leaflet popup (and detail overlay) when activeReportId changes
  // from outside ReportDots (e.g. sidebar click). Skip for dot-initiated changes.
  useEffect(() => {
    if (dotClickRef.current) {
      dotClickRef.current = false;
      return;
    }
    map.closePopup();
    setDetailState(null);
  }, [activeReportId, map]);

  useEffect(() => {
    if (!detailState) { setDetailPos(null); return; }
    const update = () => {
      const pt = map.latLngToContainerPoint(L.latLng(detailState.lat, detailState.lon));
      const rect = map.getContainer().getBoundingClientRect();
      setDetailPos({ x: rect.left + pt.x, y: rect.top + pt.y });
    };
    update();
    map.on('move zoom moveend zoomend', update);
    return () => { map.off('move zoom moveend zoomend', update); };
  }, [detailState, map]);

  const openDetail = useCallback((dot: DotDTO, lat: number, lon: number, reopenPopup: () => void) => {
    setDetailState({ dot, lat, lon, reopenPopup });
  }, []);

  // Close detail overlay and clear active marker.
  const closeDetail = useCallback(() => {
    setDetailState(null);
    setActiveReportId(null);
  }, [setActiveReportId]);

  // Close detail overlay when clicking on the map outside it.
  useEffect(() => {
    if (!detailState) return;
    const handler = () => closeDetail();
    const t = window.setTimeout(() => { map.on('click', handler); }, 0);
    return () => {
      window.clearTimeout(t);
      map.off('click', handler);
    };
  }, [detailState?.dot.report_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Back: close detail, clear active, reopen aggregate popup.
  const backToList = useCallback(() => {
    dotClickRef.current = true; // prevent useEffect from closing the just-reopened popup
    const prevDetail = detailState;
    setDetailState(null);
    setActiveReportId(null);
    if (prevDetail) prevDetail.reopenPopup();
  }, [setActiveReportId, detailState]);

  return (
    <>
      {groups.map((group) => {
        const key = `${group.lat.toFixed(5)},${group.lon.toFixed(5)}`;
        return (
          <GroupMarker
            key={key}
            group={group}
            groupKey={key}
            activeReportId={activeReportId}
            activeGroupKeyRef={activeGroupKeyRef}
            username={username}
            map={map}
            didSelectRef={didSelectRef}
            dotClickRef={dotClickRef}
            reports={reports}
            setActiveReportId={setActiveReportId}
            optimisticAcknowledge={optimisticAcknowledge}
            openDetail={openDetail}
            closeDetail={closeDetail}
          />
        );
      })}
      {detailState && detailPos && (
        <DetailOverlay
          dot={detailState.dot}
          pos={detailPos}
          onClose={closeDetail}
          onBack={backToList}
        />
      )}
    </>
  );
}
