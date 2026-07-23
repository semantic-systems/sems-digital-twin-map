import React, { useMemo, useRef, useEffect, useCallback, useState } from 'react';
import ReactDOM from 'react-dom';
import { Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { hideReport, flagReport, acknowledgeReport } from '../../api/reports';
import { t } from '../../i18n';
import type { DotDTO } from '../../types';
import { computeVisibleReportBounds } from '../../utils/geo';
import { useMapStore } from '../../store/useMapStore';
import { useTourStore } from '../../store/useTourStore';
import { EXAMPLE_IDENTIFIER } from '../../tour/constants';

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
  // Pixel-cell bucket key (e.g. "12,7") — used ONLY internally by clusterDots'
  // cache Map. It is inherently zoom-dependent (a fixed lat/lon falls in a
  // different pixel cell at every zoom level), so it must NEVER be used as a
  // React key or GroupMarker's groupKey — doing so once caused every marker to
  // fully unmount/remount (closing any open popup) on every zoom change.
  key: string;
  // Stable geographic identity ("lat.toFixed(5),lon.toFixed(5)") — used for
  // React's key and groupKey. As long as a cell's dot membership doesn't change
  // across a zoom step, this stays identical, so the marker (and its popup)
  // survives the zoom.
  identityKey: string;
  lat: number;
  lon: number;
  dots: DotDTO[];
}

// Everything about a cell's dots that affects how its marker renders. If this is
// unchanged, the cached group object is reused so React.memo(GroupMarker) skips it.
function groupSignature(dots: DotDTO[]): string {
  return dots
    .map((d) => `${d.report_id}|${d.relevance}|${d.new ? 1 : 0}|${d.flag ? 1 : 0}|${d.hide ? 1 : 0}|${d.seen ? 1 : 0}`)
    .sort()
    .join(';');
}

// Grid-cluster dots into per-cell groups. `cache` (keyed by pixel cell) lets an
// unchanged cell keep its previous DotGroup *reference* across refreshes — the
// whole point of item 3: on new dots, only cells that actually changed produce a
// new group, so untouched markers are never re-rendered or rebuilt in the DOM.
function clusterDots(
  dots: DotDTO[],
  leafletMap: L.Map,
  cache: Map<string, { sig: string; group: DotGroup }>,
  exampleReportId: number | null,
  cellSize = 60,
): DotGroup[] {
  const cellMap = new Map<string, DotDTO[]>();
  for (const dot of dots) {
    let key: string;
    if (exampleReportId !== null && dot.report_id === exampleReportId) {
      // Always its own isolated cell, keyed per-location (not just per-report,
      // since the example has two) so Hamburg and Berlin never merge into one
      // "2" marker either. Letting it cluster with a nearby real dot the
      // normal pixel-cell way would make its group's identity — and so its
      // React key, and so the underlying Leaflet marker DOM element — shift
      // whenever that real dot joins or leaves the cluster across a zoom
      // change. The tour's own auto-centering (the "dot" step) does exactly
      // that, and a step still attached to the old, now-detached marker
      // collapses its tooltip to a 0,0 fallback position.
      key = `example-${dot.report_id}-${dot.lat}-${dot.lon}`;
    } else {
      const px = leafletMap.latLngToContainerPoint([dot.lat, dot.lon]);
      key = `${Math.floor(px.x / cellSize)},${Math.floor(px.y / cellSize)}`;
    }
    if (!cellMap.has(key)) cellMap.set(key, []);
    cellMap.get(key)!.push(dot);
  }

  const next = new Map<string, { sig: string; group: DotGroup }>();
  const result: DotGroup[] = [];
  for (const [key, group] of cellMap) {
    const sig = groupSignature(group);
    const cached = cache.get(key);
    if (cached && cached.sig === sig) {
      // Same cell, same rendering-relevant content → reuse the stable reference.
      next.set(key, cached);
      result.push(cached.group);
      continue;
    }
    const lat = group.reduce((s, d) => s + d.lat, 0) / group.length;
    const lon = group.reduce((s, d) => s + d.lon, 0) / group.length;
    const identityKey = `${lat.toFixed(5)},${lon.toFixed(5)}`;
    const g: DotGroup = { key, identityKey, lat, lon, dots: group };
    next.set(key, { sig, group: g });
    result.push(g);
  }

  // Replace the cache contents in place so dropped cells are evicted.
  cache.clear();
  for (const [k, v] of next) cache.set(k, v);
  return result;
}

// ---------------------------------------------------------------------------
// DivIcon factory
// ---------------------------------------------------------------------------

function makeDotIcon({
  color, size, count, hasNew, isActive, dataTour, dimmed = false,
}: {
  color: string; size: number; count: number; hasNew: boolean; isActive: boolean; dataTour?: string; dimmed?: boolean;
}): L.DivIcon {
  const borderWidth = isActive ? 3 : 2;
  const countBadge = count > 1
    ? `<div style="position:absolute;top:-8px;right:-8px;background:#1f2937;color:#fff;font-size:9px;font-weight:700;font-family:'Inter',sans-serif;border-radius:999px;padding:1px 5px;min-width:16px;text-align:center;line-height:1.5;border:1.5px solid #fff;pointer-events:none;">${count}</div>`
    : '';
  const exclamation = hasNew && !isActive
    ? `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;font-size:${Math.round(size * 0.55)}px;font-weight:900;color:#fff;font-family:'Inter',sans-serif;line-height:1;text-shadow:0 1px 2px rgba(0,0,0,0.4);">!</div>`
    : '';
  // Hidden reports (surfaced only under show-hidden) render dimmed so they read
  // as "hidden but visible for review", mirroring the sidebar list's greying.
  return L.divIcon({
    html: `<div${dataTour ? ` data-tour="${dataTour}"` : ''} style="position:relative;width:${size}px;height:${size}px;${dimmed ? 'opacity:0.4;' : ''}">
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
  const { optimisticHide, optimisticFlag, reports, dots, pinnedReport } = useReportStore();
  const { requestFitBounds } = useMapStore();
  // Prefer the loaded page; else the pinned report (ReportList fetches it on
  // demand when a selected report is beyond the page — clicking the dot triggers
  // exactly that, so this resolves once the fetch lands and gives the popup live
  // hide/flag state + report-based centering instead of the dot's snapshot).
  const report = reports.find((r) => r.id === dot.report_id)
    ?? (pinnedReport?.id === dot.report_id ? pinnedReport : undefined);

  // If neither is available yet, fall back to the dot's own hide/flag snapshot so
  // the action buttons still render and work.
  const hidden = report ? report.user_state.hide : dot.hide;
  const flagged = report ? report.user_state.flag : dot.flag;

  const handleCenter = () => {
    const groupDots = dots.filter((d) => d.report_id === dot.report_id);
    const locs = report?.user_state.locations ?? report?.locations ?? [];
    const bounds = computeVisibleReportBounds(groupDots, locs);
    if (bounds) {
      requestFitBounds(bounds);
    } else if (dot.location_bbox) {
      const [s, n, w, e] = dot.location_bbox;
      requestFitBounds([[s, w], [n, e]]);
    } else {
      requestFitBounds([[dot.lat - 0.01, dot.lon - 0.01], [dot.lat + 0.01, dot.lon + 0.01]]);
    }
  };

  const handleHide = async () => {
    if (!username) return;
    const newHide = !hidden;
    optimisticHide(dot.report_id, newHide);
    try { await hideReport(dot.report_id, newHide); }
    catch (e) { console.error('Failed to hide:', e); }
  };

  const handleFlag = async () => {
    if (!username || !dot.author) return;
    const newFlag = !flagged;
    optimisticFlag(dot.author, newFlag);
    try { await flagReport(dot.report_id, newFlag); }
    catch (e) { console.error('Failed to flag:', e); }
  };

  const btn: React.CSSProperties = {
    fontSize: 11, padding: '2px 8px', borderRadius: 4,
    border: '1px solid #d1d5db', background: '#f3f4f6', color: '#374151',
    cursor: 'pointer', fontFamily: "'Inter', system-ui, sans-serif",
    whiteSpace: 'nowrap',
  };

  return (
    <div style={{ maxWidth: 320, fontFamily: "'Inter', system-ui, sans-serif" }}>
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
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        <a href={dot.url} target="_blank" rel="noopener noreferrer"
          style={{ ...btn, textDecoration: 'none', display: 'inline-block' }}>
          {t('open')}
        </a>
        <button onClick={handleCenter} title={t('center_title')} style={btn}>
          {t('center')}
        </button>
        <button onClick={handleHide} style={btn}>
          {hidden ? t('unhide') : t('hide')}
        </button>
        {dot.author && (
          <button onClick={handleFlag} style={btn}>
            {flagged ? t('unflag') : t('flag')}
          </button>
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
  setActiveReportId: (id: number | null) => void;
  optimisticAcknowledge: (id: number) => void;
  openDetail: (dot: DotDTO, lat: number, lon: number, reopenPopup: () => void) => void;
  closeDetail: () => void;
  /** The onboarding tour's example report's real id, if it's currently loaded — see exampleReport.ts. */
  exampleReportId: number | null;
}

const GroupMarker = React.memo(function GroupMarker({
  group, groupKey, activeReportId, activeGroupKeyRef, username, map,
  didSelectRef, dotClickRef,
  setActiveReportId, optimisticAcknowledge,
  openDetail, closeDetail, exampleReportId,
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

  // Dim the marker only when every report in the group is hidden — a group that
  // still contains a visible report reads as visible.
  const allHidden = dedupedDots.every((d) => d.hide || d.seen);

  // Tag the onboarding tour's example dot (and only that dot) so the tour can
  // point at a real, live marker instead of a decorative stand-in.
  const isExampleGroup = exampleReportId !== null && group.dots.some((d) => d.report_id === exampleReportId);

  const icon = useMemo(
    () => makeDotIcon({ color, size, count: dedupedDots.length, hasNew, isActive: isGroupActive, dataTour: isExampleGroup ? 'tour-example-dot' : undefined, dimmed: allHidden }),
    [color, size, dedupedDots.length, hasNew, isGroupActive, isExampleGroup, allHidden],
  );

  // Ref to the Leaflet Marker instance so we can reopen the popup programmatically.
  const markerRef = useRef<L.Marker>(null);

  // Mutable ref so stable closures always see latest values.
  const s = useRef({
    isMulti, group, dedupedDots, groupKey, activeReportId, activeGroupKeyRef, username,
    setActiveReportId, optimisticAcknowledge,
    didSelectRef, dotClickRef, map, exampleReportId,
    openDetail, closeDetail, markerRef,
  });
  s.current = {
    isMulti, group, dedupedDots, groupKey, activeReportId, activeGroupKeyRef, username,
    setActiveReportId, optimisticAcknowledge,
    didSelectRef, dotClickRef, map, exampleReportId,
    openDetail, closeDetail, markerRef,
  };

  // Identity-stable event handlers — useEventHandlers never removes/re-adds them.
  const eventHandlers = useMemo(() => ({
    click: () => {
      const { isMulti, dedupedDots, groupKey, activeReportId, activeGroupKeyRef, username, dotClickRef, setActiveReportId, optimisticAcknowledge, exampleReportId } = s.current;
      if (!isMulti) {
        const dot = dedupedDots[0];
        // While the tour's "dot" step is showing, clicking the example dot
        // still opens its Leaflet popup natively — but selecting it here
        // would restyle this marker (bigger, blue, "!" gone), and Leaflet
        // swaps in a new icon DOM element for that, invalidating the tour's
        // cached reference to this one (its tooltip collapses to a 0,0
        // fallback position). The tour selects it for real moments later,
        // on the next step, once that restyle can't strand anything.
        if (dot.report_id === exampleReportId && useTourStore.getState().dotStepActive) {
          return;
        }
        // Only deactivate when clicking the exact same marker that's already active.
        // A different dot of the same report (different position) keeps the report active.
        const isSameMarker = dot.report_id === activeReportId && activeGroupKeyRef.current === groupKey;
        const newId = isSameMarker ? null : dot.report_id;
        activeGroupKeyRef.current = newId !== null ? groupKey : null;
        dotClickRef.current = true;
        setActiveReportId(newId);
        if (newId !== null && username && dot.new) {
          optimisticAcknowledge(newId);
          acknowledgeReport(newId).catch(() => {});
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
      const { didSelectRef, setActiveReportId, dedupedDots, exampleReportId } = s.current;
      // Same suppression as the click handler: while the example dot's own
      // selection is being held off during the tour's "dot" step, its popup
      // closing (e.g. the tour advancing) must not deselect whatever report
      // — the tour's example or an unrelated one the user already had open —
      // is actually selected right now.
      const isExampleDot = dedupedDots.some((d) => d.report_id === exampleReportId);
      if (isExampleDot && useTourStore.getState().dotStepActive) {
        didSelectRef.current = false;
        return;
      }
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
      acknowledgeReport(dot.report_id).catch(() => {});
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
      <Popup autoPan={false} maxWidth={340} minWidth={300}>
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

export function ReportDots({ visibleDots }: { visibleDots: DotDTO[] }): React.ReactElement {
  const map = useMap();
  const { activeReportId, setActiveReportId, optimisticAcknowledge, reports } = useReportStore();
  const { username } = useUserStore();

  const exampleReportId = useMemo(
    () => reports.find((r) => r.identifier === EXAMPLE_IDENTIFIER)?.id ?? null,
    [reports],
  );

  const [zoom, setZoom] = useState(() => map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });

  // Persists group object references across refreshes so unchanged cells don't
  // re-render (see clusterDots). Lives in a ref, not state — mutating it must not
  // itself trigger a render.
  const groupCacheRef = useRef<Map<string, { sig: string; group: DotGroup }>>(new Map());
  const groups = useMemo(() => clusterDots(visibleDots, map, groupCacheRef.current, exampleReportId), [visibleDots, zoom, exampleReportId]); // eslint-disable-line react-hooks/exhaustive-deps
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

  // Close detail overlay when clicking on the map outside it. Leaflet's own
  // 'click' listener on the map container fires BEFORE React's synthetic click
  // dispatch for any DOM node nested inside it (React's delegated listener
  // sits higher, at the app root) — so a click on one of our own floating
  // controls (e.g. an offscreen-navigation arrow) reaches this handler too,
  // and calling stopPropagation() inside that control's own onClick is too
  // late to prevent it. Checking the actual click target here — instead of
  // relying on propagation — is what correctly distinguishes "clicked the
  // bare map" from "clicked one of our own overlays".
  useEffect(() => {
    if (!detailState) return;
    const handler = (e: L.LeafletMouseEvent) => {
      const target = e.originalEvent?.target as HTMLElement | null;
      if (target?.closest('[data-offscreen-arrow]')) return;
      closeDetail();
    };
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
      {groups.map((group) => (
        <GroupMarker
          key={group.identityKey}
          group={group}
          groupKey={group.identityKey}
          activeReportId={activeReportId}
          activeGroupKeyRef={activeGroupKeyRef}
          username={username}
          map={map}
          didSelectRef={didSelectRef}
          dotClickRef={dotClickRef}
          setActiveReportId={setActiveReportId}
          optimisticAcknowledge={optimisticAcknowledge}
          openDetail={openDetail}
          closeDetail={closeDetail}
          exampleReportId={exampleReportId}
        />
      ))}
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
