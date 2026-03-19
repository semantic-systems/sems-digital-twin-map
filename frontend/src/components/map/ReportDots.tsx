import React, { useMemo, useRef, useEffect } from 'react';
import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { hideReport, flagReport, acknowledgeReport } from '../../api/reports';
import { t } from '../../i18n';
import type { DotDTO } from '../../types';

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
  color,
  size,
  count,
  hasNew,
  isActive,
}: {
  color: string;
  size: number;
  count: number;
  hasNew: boolean;
  isActive: boolean;
}): L.DivIcon {
  const borderColor = '#ffffff';
  const borderWidth = isActive ? 3 : 2;

  const countBadge =
    count > 1
      ? `<div style="position:absolute;top:-8px;right:-8px;background:#1f2937;color:#fff;font-size:9px;font-weight:700;font-family:'Inter',sans-serif;border-radius:999px;padding:1px 5px;min-width:16px;text-align:center;line-height:1.5;border:1.5px solid #fff;pointer-events:none;">${count}</div>`
      : '';

  // Amber ring around the dot when any event is "new"
  const newRing = hasNew && !isActive
    ? `<div style="position:absolute;inset:-5px;border-radius:50%;border:2.5px solid #fbbf24;pointer-events:none;"></div>`
    : '';

  return L.divIcon({
    html: `<div style="position:relative;width:${size}px;height:${size}px;">
      ${newRing}
      <div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:${borderWidth}px solid ${borderColor};box-sizing:border-box;box-shadow:0 1px 4px rgba(0,0,0,0.45);"></div>
      ${countBadge}
    </div>`,
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -(size / 2 + 6)],
  });
}

// ---------------------------------------------------------------------------
// Single-dot popup
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
    catch (e) { console.error('Failed to hide from dot:', e); }
  };

  const handleFlag = async () => {
    if (!username || !dot.author || !report) return;
    const newFlag = !report.user_state.flag;
    optimisticFlag(dot.author, newFlag);
    try { await flagReport(dot.report_id, username, newFlag); }
    catch (e) { console.error('Failed to flag from dot:', e); }
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
// Multi-dot popup
// ---------------------------------------------------------------------------

interface MultiDotPopupHandle { reset: () => void; }

const MultiDotPopup = React.forwardRef<MultiDotPopupHandle, {
  dots: DotDTO[];
  onSelect: (dot: DotDTO) => void;
  onBack: () => void;
}>(function MultiDotPopupInner({ dots, onSelect, onBack }, ref) {
  const [selectedDot, setSelectedDot] = React.useState<DotDTO | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  React.useImperativeHandle(ref, () => ({
    reset: () => setSelectedDot(null),
  }));

  useEffect(() => {
    if (containerRef.current) L.DomEvent.disableClickPropagation(containerRef.current);
  }, []);

  const handleRowClick = (dot: DotDTO) => {
    setSelectedDot(dot);
    onSelect(dot);
  };

  const handleBack = () => {
    setSelectedDot(null);
    onBack();
  };

  const rowStyle: React.CSSProperties = {
    cursor: 'pointer', borderRadius: 4, padding: '4px 6px',
    borderBottom: '1px solid #f3f4f6',
  };

  return (
    <div ref={containerRef} style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      {selectedDot ? (
        <div style={{ maxWidth: 280 }}>
          <button
            onClick={handleBack}
            style={{
              display: 'flex', alignItems: 'center', gap: 3, width: '100%',
              fontSize: 10, color: '#6b7280', background: 'none', border: 'none',
              padding: '0 0 6px', marginBottom: 6, cursor: 'pointer',
              borderBottom: '1px solid #e5e7eb',
            }}
          >
            ← {dots.length} Ereignisse an diesem Ort
          </button>
          <DotPopup dot={selectedDot} />
        </div>
      ) : (
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
                onClick={() => handleRowClick(dot)}
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
                    border: '1px solid rgba(0,0,0,0.15)',
                    display: 'inline-block',
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
      )}
    </div>
  );
});

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ReportDots(): React.ReactElement {
  const { dots, activeReportId, setActiveReportId, optimisticAcknowledge, reports } = useReportStore();
  const { username } = useUserStore();

  const groups = useMemo(() => groupDots(dots), [dots]);
  // Refs to each MultiDotPopup so popupopen can reset it to the list view.
  const multiPopupRefs = useRef<Map<string, MultiDotPopupHandle>>(new Map());
  // True while a row was selected in the current popup session so popupclose
  // knows not to clear activeReportId.
  const didSelectRef = useRef(false);

  return (
    <>
      {groups.map((group) => {
        const key = `${group.lat.toFixed(5)},${group.lon.toFixed(5)}`;
        const isGroupActive = group.dots.some((d) => d.report_id === activeReportId);
        const hasNew = group.dots.some((d) => d.new);
        const isMulti = group.dots.length > 1;

        // Pick highest-relevance dot to set the group color
        const primaryDot = [...group.dots].sort(
          (a, b) => (RELEVANCE_ORDER[a.relevance] ?? 3) - (RELEVANCE_ORDER[b.relevance] ?? 3),
        )[0];

        const color = isGroupActive ? '#3b82f6' : (RELEVANCE_COLORS[primaryDot.relevance] ?? '#6b7280');
        const size = isGroupActive ? 26 : isMulti ? 24 : 20;

        const icon = makeDotIcon({ color, size, count: group.dots.length, hasNew, isActive: isGroupActive });

        return (
          <Marker
            key={key}
            position={[group.lat, group.lon]}
            icon={icon}
            eventHandlers={{
              click: () => {
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
                didSelectRef.current = false;
                multiPopupRefs.current.get(key)?.reset();
              },
              popupclose: () => {
                if (!didSelectRef.current) setActiveReportId(null);
                didSelectRef.current = false;
              },
            }}
          >
            <Popup closeOnClick={false}>
              {isMulti
                ? <MultiDotPopup
                    ref={(handle) => {
                      if (handle) multiPopupRefs.current.set(key, handle);
                      else multiPopupRefs.current.delete(key);
                    }}
                    dots={group.dots}
                    onSelect={(dot) => {
                      didSelectRef.current = true;
                      setActiveReportId(dot.report_id);
                      if (dot.new && username) {
                        optimisticAcknowledge(dot.report_id);
                        acknowledgeReport(dot.report_id, username).catch(() => {});
                      }
                    }}
                    onBack={() => {
                      didSelectRef.current = false;
                      setActiveReportId(null);
                    }}
                  />
                : <DotPopup dot={group.dots[0]} />}
            </Popup>
          </Marker>
        );
      })}
    </>
  );
}
