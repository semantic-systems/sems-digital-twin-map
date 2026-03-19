import React, { useMemo, useRef, useEffect, useCallback, useState } from 'react';
import ReactDOM from 'react-dom';
import { Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { hideReport, flagReport, acknowledgeReport } from '../../api/reports';
import { t } from '../../i18n';
import type { DotDTO, ReportDTO } from '../../types';

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

function groupDots(dots: DotDTO[]): DotGroup[] {
  const map = new Map<string, DotDTO[]>();
  for (const dot of dots) {
    const key = `${dot.lat.toFixed(5)},${dot.lon.toFixed(5)}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(dot);
  }
  return Array.from(map.values()).map((g) => ({ lat: g[0].lat, lon: g[0].lon, dots: g }));
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
  const newRing = hasNew && !isActive
    ? `<div style="position:absolute;inset:-5px;border-radius:50%;border:2.5px solid #fbbf24;pointer-events:none;"></div>`
    : '';
  return L.divIcon({
    html: `<div style="position:relative;width:${size}px;height:${size}px;">
      ${newRing}
      <div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:${borderWidth}px solid #ffffff;box-sizing:border-box;box-shadow:0 1px 4px rgba(0,0,0,0.45);"></div>
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
      <p style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
        {dot.event_type} · {dot.timestamp}
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
                {dot.author ? `@${dot.author} · ` : ''}{dot.platform} · {dot.event_type} · {dot.timestamp}
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
  reportId, pos, onClose, onBack,
}: {
  reportId: number;
  pos: { x: number; y: number };
  onClose: () => void;
  onBack: () => void;
}): React.ReactElement | null {
  // Always read the latest dot from the store so we reflect optimistic updates.
  const { dots } = useReportStore();
  const dot = dots.find((d) => d.report_id === reportId);
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
  activeReportId: number | null;
  username: string | null;
  map: L.Map;
  didSelectRef: React.MutableRefObject<boolean>;
  mapClickHandlerRef: React.MutableRefObject<(() => void) | null>;
  reports: ReportDTO[];
  setActiveReportId: (id: number | null) => void;
  optimisticAcknowledge: (id: number) => void;
  openDetail: (reportId: number, lat: number, lon: number, reopenPopup: () => void) => void;
  closeDetail: () => void;
}

const GroupMarker = React.memo(function GroupMarker({
  group, activeReportId, username, map,
  didSelectRef, mapClickHandlerRef,
  reports, setActiveReportId, optimisticAcknowledge,
  openDetail, closeDetail,
}: GroupMarkerProps) {
  const key = `${group.lat.toFixed(5)},${group.lon.toFixed(5)}`;
  const isGroupActive = group.dots.some((d) => d.report_id === activeReportId);
  const hasNew = group.dots.some((d) => d.new);
  const isMulti = group.dots.length > 1;

  const primaryDot = useMemo(
    () => [...group.dots].sort(
      (a, b) => (RELEVANCE_ORDER[a.relevance] ?? 3) - (RELEVANCE_ORDER[b.relevance] ?? 3),
    )[0],
    [group.dots],
  );

  const color = isGroupActive ? '#3b82f6' : (RELEVANCE_COLORS[primaryDot.relevance] ?? '#6b7280');
  const size = isGroupActive ? 26 : isMulti ? 24 : 20;

  const icon = useMemo(
    () => makeDotIcon({ color, size, count: group.dots.length, hasNew, isActive: isGroupActive }),
    [color, size, group.dots.length, hasNew, isGroupActive],
  );

  // Ref to the Leaflet Marker instance so we can reopen the popup programmatically.
  const markerRef = useRef<L.Marker>(null);

  // Mutable ref so stable closures always see latest values.
  const s = useRef({
    isMulti, group, activeReportId, username, reports,
    setActiveReportId, optimisticAcknowledge,
    didSelectRef, mapClickHandlerRef, map,
    openDetail, closeDetail, markerRef,
  });
  s.current = {
    isMulti, group, activeReportId, username, reports,
    setActiveReportId, optimisticAcknowledge,
    didSelectRef, mapClickHandlerRef, map,
    openDetail, closeDetail, markerRef,
  };

  // Identity-stable event handlers — useEventHandlers never removes/re-adds them.
  const eventHandlers = useMemo(() => ({
    click: () => {
      const { isMulti, group, activeReportId, username, reports, setActiveReportId, optimisticAcknowledge } = s.current;
      if (!isMulti) {
        const dot = group.dots[0];
        const newId = dot.report_id === activeReportId ? null : dot.report_id;
        setActiveReportId(newId);
        if (newId !== null && username) {
          const report = reports.find((r) => r.id === newId);
          if (report?.user_state.new) {
            optimisticAcknowledge(newId);
            acknowledgeReport(newId, username).catch(() => {});
          }
        }
      }
    },
    popupopen: () => {
      const { isMulti, didSelectRef, mapClickHandlerRef, map, closeDetail } = s.current;
      if (isMulti) {
        closeDetail(); // close any open detail overlay
        didSelectRef.current = false;
        const handler = () => map.closePopup();
        mapClickHandlerRef.current = handler;
        setTimeout(() => {
          if (s.current.mapClickHandlerRef.current === handler) {
            s.current.map.on('click', handler);
          }
        }, 0);
      }
    },
    popupclose: () => {
      const { mapClickHandlerRef, didSelectRef, setActiveReportId, map } = s.current;
      if (mapClickHandlerRef.current) {
        map.off('click', mapClickHandlerRef.current);
        mapClickHandlerRef.current = null;
      }
      if (!didSelectRef.current) setActiveReportId(null);
      didSelectRef.current = false;
    },
  }), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Stable onSelect: closes the Leaflet popup FIRST, then triggers store updates.
  const onSelect = useCallback((dot: DotDTO) => {
    const { didSelectRef, map, setActiveReportId, username, optimisticAcknowledge, group, openDetail, markerRef } = s.current;
    didSelectRef.current = true;
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
    openDetail(dot.report_id, group.lat, group.lon, reopenPopup);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Marker ref={markerRef} position={[group.lat, group.lon]} icon={icon} eventHandlers={eventHandlers}>
      <Popup closeOnClick={isMulti ? false : undefined}>
        {isMulti
          ? <MultiDotPopup dots={group.dots} onSelect={onSelect} />
          : <DotPopup dot={group.dots[0]} />}
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

  const groups = useMemo(() => groupDots(dots), [dots]);
  const didSelectRef = useRef(false);
  const mapClickHandlerRef = useRef<(() => void) | null>(null);

  // Detail overlay state — separate from Leaflet popup system entirely.
  const [detailState, setDetailState] = useState<{
    reportId: number; lat: number; lon: number; reopenPopup: () => void;
  } | null>(null);
  const [detailPos, setDetailPos] = useState<{ x: number; y: number } | null>(null);

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

  const openDetail = useCallback((reportId: number, lat: number, lon: number, reopenPopup: () => void) => {
    setDetailState({ reportId, lat, lon, reopenPopup });
  }, []);

  // Close detail overlay and clear active marker.
  const closeDetail = useCallback(() => {
    setDetailState(null);
    setActiveReportId(null);
  }, [setActiveReportId]);

  // Back: close detail, clear active, reopen aggregate popup.
  const backToList = useCallback(() => {
    setDetailState((prev) => {
      if (prev) prev.reopenPopup();
      return null;
    });
    setActiveReportId(null);
  }, [setActiveReportId]);

  return (
    <>
      {groups.map((group) => {
        const key = `${group.lat.toFixed(5)},${group.lon.toFixed(5)}`;
        return (
          <GroupMarker
            key={key}
            group={group}
            activeReportId={activeReportId}
            username={username}
            map={map}
            didSelectRef={didSelectRef}
            mapClickHandlerRef={mapClickHandlerRef}
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
          reportId={detailState.reportId}
          pos={detailPos}
          onClose={closeDetail}
          onBack={backToList}
        />
      )}
    </>
  );
}
