import React, { useState, useRef } from 'react';
import ReactDOM from 'react-dom';
import { t } from '../../i18n';
import { useFilterStore, ALL_RELEVANCES_LIST, getLayerColor } from '../../store/useFilterStore';
import { useReportStore } from '../../store/useReportStore';
import { EventTypeChips } from './EventTypeChips';
import { PRESET_AREAS } from '../../utils/presetAreas';

const RELEVANCE_COLORS: Record<string, string> = {
  high: '#ef4444',
  medium: '#f97316',
  low: '#ca8a04',
  none: '#6b7280',
};

const fmtCount = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k` : String(n);

const pad = (n: number) => String(n).padStart(2, '0');

/** ISO string → "YYYY-MM-DD" in local time, for a date input value. */
const isoToDateInput = (iso: string | null): string => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

/** ISO string → "HH:mm" in local time, for a time input value. */
const isoToTimeInput = (iso: string | null): string => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/** Combine a date string ("YYYY-MM-DD") and time string ("HH:mm") into an ISO UTC string. */
const combineDateTimeToIso = (date: string, time: string): string | null => {
  if (!date) return null;
  const d = new Date(`${date}T${time || '00:00'}`);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
};

/** Compact "24.06. 14:30" style label for a custom-range pill. */
const fmtRangeLabel = (iso: string | null): string => {
  if (!iso) return '…';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '…';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}. ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const Divider = () => (
  <div
    style={{
      width: 1,
      height: 28,
      background: '#e5e7eb',
      flexShrink: 0,
      margin: '0 8px',
    }}
  />
);

const SectionLabel = ({ children }: { children: React.ReactNode }) => (
  <span
    style={{
      fontSize: 10,
      fontWeight: 600,
      color: '#9ca3af',
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
      whiteSpace: 'nowrap',
    }}
  >
    {children}
  </span>
);

export function FilterBar(): React.ReactElement {
  const TIME_WINDOWS = [
    { key: '1h', label: '1h' },
    { key: '6h', label: '6h' },
    { key: '1d', label: '1d' },
    { key: '3d', label: '3d' },
    { key: 'all', label: t('all') },
  ];

  const {
    locShowLocalized,
    locShowPending,
    locShowUnlocalized,
    setLocShowLocalized,
    setLocShowPending,
    setLocShowUnlocalized,
    relevances,
    setRelevances,
    platforms,
    allPlatforms,
    setPlatforms,
    showHidden,
    setShowHidden,
    showFlagged,
    setShowFlagged,
    showUnflagged,
    setShowUnflagged,
    timeWindow,
    setTimeWindow,
    customSince,
    customUntil,
    setCustomRange,
    activeLayers,
    availableLayers,
    toggleLayer,
    spatialPolygon,
    spatialDrawMode,
    setSpatialPolygon,
    setSpatialDrawMode,
  } = useFilterStore();

  const { eventTypeTotals, relevanceTotals, locationCounts } = useReportStore();
  const { platformCounts } = useFilterStore();

  // Custom-range popover state
  const [rangeOpen, setRangeOpen] = useState(false);
  const [rangePos, setRangePos] = useState<{ x: number; y: number } | null>(null);
  const [draftSinceDate, setDraftSinceDate] = useState('');
  const [draftSinceTime, setDraftSinceTime] = useState('');
  const [draftUntilDate, setDraftUntilDate] = useState('');
  const [draftUntilTime, setDraftUntilTime] = useState('');
  const rangeBtnRef = useRef<HTMLButtonElement>(null);

  const openRangePicker = () => {
    setDraftSinceDate(isoToDateInput(customSince));
    setDraftSinceTime(isoToTimeInput(customSince));
    setDraftUntilDate(isoToDateInput(customUntil));
    setDraftUntilTime(isoToTimeInput(customUntil));
    const rect = rangeBtnRef.current?.getBoundingClientRect();
    setRangePos(rect ? { x: rect.left, y: rect.bottom + 6 } : { x: 200, y: 64 });
    setRangeOpen(true);
  };

  const applyRange = () => {
    setCustomRange(
      combineDateTimeToIso(draftSinceDate, draftSinceTime),
      combineDateTimeToIso(draftUntilDate, draftUntilTime),
    );
    setRangeOpen(false);
  };

  const isCustomActive = timeWindow === 'custom';

  const toggleRelevance = (rel: string) => {
    if (relevances.includes(rel)) {
      setRelevances(relevances.filter((r) => r !== rel));
    } else {
      setRelevances([...relevances, rel]);
    }
  };

  const togglePlatform = (p: string) => {
    if (platforms.includes(p)) {
      setPlatforms(platforms.filter((x) => x !== p));
    } else {
      setPlatforms([...platforms, p]);
    }
  };

  const effectivePlatforms = allPlatforms.length ? allPlatforms : [];

  const row: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'nowrap',
    gap: 0,
    width: '100%',
    minHeight: 28,
  };

  const checkLabel: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 3,
    cursor: 'pointer',
    fontSize: 11,
    color: '#374151',
    whiteSpace: 'nowrap',
  };

  return (
    <div
      data-app-region="filterbar"
      style={{
        background: '#ffffff',
        borderBottom: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
    >
      {/* Row 1: Location · Relevance */}
      <div style={{ ...row, padding: '4px 12px', borderBottom: '1px solid #f3f4f6', overflowX: 'auto' }}>
        <SectionLabel>{t('location')}</SectionLabel>
        <div style={{ display: 'flex', gap: 10, marginLeft: 6, alignItems: 'center' }}>
          <label style={checkLabel}>
            <input type="checkbox" checked={locShowLocalized} onChange={(e) => setLocShowLocalized(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('loc_located')}
            {(locationCounts['localized'] ?? 0) > 0 && <span style={{ color: '#9ca3af', fontWeight: 400 }}>({fmtCount(locationCounts['localized']!)})</span>}
          </label>
          <label style={checkLabel}>
            <input type="checkbox" checked={locShowPending} onChange={(e) => setLocShowPending(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('loc_pending')}
            {(locationCounts['pending'] ?? 0) > 0 && <span style={{ color: '#9ca3af', fontWeight: 400 }}>({fmtCount(locationCounts['pending']!)})</span>}
          </label>
          <label style={checkLabel}>
            <input type="checkbox" checked={locShowUnlocalized} onChange={(e) => setLocShowUnlocalized(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('loc_none')}
            {(locationCounts['unlocalized'] ?? 0) > 0 && <span style={{ color: '#9ca3af', fontWeight: 400 }}>({fmtCount(locationCounts['unlocalized']!)})</span>}
          </label>
        </div>

        <Divider />

        <SectionLabel>{t('relevance')}</SectionLabel>
        <div style={{ display: 'flex', gap: 6, marginLeft: 6, alignItems: 'center' }}>
          {ALL_RELEVANCES_LIST.map((rel) => (
            <label
              key={rel}
              style={{ ...checkLabel, color: RELEVANCE_COLORS[rel], fontWeight: 600 }}
            >
              <input
                type="checkbox"
                checked={relevances.includes(rel)}
                onChange={() => toggleRelevance(rel)}
                style={{ accentColor: RELEVANCE_COLORS[rel], width: 12, height: 12 }}
              />
              {t(`rel_${rel}`)}
              {(relevanceTotals[rel] ?? 0) > 0 && (
                <span style={{ color: '#9ca3af', fontWeight: 400 }}>({fmtCount(relevanceTotals[rel]!)})</span>
              )}
            </label>
          ))}
        </div>

        <Divider />

        <SectionLabel>{t('time')}</SectionLabel>
        <div style={{ display: 'flex', gap: 3, marginLeft: 6, alignItems: 'center', position: 'relative' }}>
          {TIME_WINDOWS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTimeWindow(key)}
              style={{
                fontSize: 11, padding: '2px 7px', borderRadius: 999,
                border: `1px solid ${timeWindow === key ? '#2563eb' : '#d1d5db'}`,
                background: timeWindow === key ? '#2563eb' : 'transparent',
                color: timeWindow === key ? '#fff' : '#374151',
                cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap',
                fontWeight: timeWindow === key ? 600 : 400,
              }}
            >
              {label}
            </button>
          ))}

          {/* Custom range pill */}
          <button
            ref={rangeBtnRef}
            onClick={openRangePicker}
            title={t('time_custom')}
            style={{
              fontSize: 11, padding: '2px 9px', borderRadius: 999,
              border: `1px solid ${isCustomActive ? '#2563eb' : '#d1d5db'}`,
              background: isCustomActive ? '#2563eb' : 'transparent',
              color: isCustomActive ? '#fff' : '#374151',
              cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap',
              fontWeight: isCustomActive ? 600 : 400,
            }}
          >
            {isCustomActive
              ? `${fmtRangeLabel(customSince)} – ${fmtRangeLabel(customUntil)}`
              : `🗓 ${t('time_custom')}`}
          </button>

          {rangeOpen && ReactDOM.createPortal(
            <>
              {/* Click-catcher backdrop */}
              <div
                onClick={() => setRangeOpen(false)}
                style={{ position: 'fixed', inset: 0, zIndex: 999 }}
              />
              <div
                style={{
                  position: 'fixed', left: rangePos?.x ?? 200, top: rangePos?.y ?? 64, zIndex: 1000,
                  background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8,
                  boxShadow: '0 4px 20px rgba(0,0,0,0.18)', padding: 12,
                  display: 'flex', flexDirection: 'column', gap: 8, minWidth: 230,
                  fontFamily: "'Inter', system-ui, sans-serif",
                }}
                onClick={(e) => e.stopPropagation()}
              >
              <div style={{ fontSize: 11, color: '#374151', display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontWeight: 600 }}>{t('time_from')}</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  <input
                    type="date"
                    value={draftSinceDate}
                    max={draftUntilDate || undefined}
                    onChange={(e) => setDraftSinceDate(e.target.value)}
                    style={{ fontSize: 11, padding: '3px 5px', border: '1px solid #d1d5db', borderRadius: 4, fontFamily: 'inherit', flex: 1 }}
                  />
                  <input
                    type="time"
                    value={draftSinceTime}
                    onChange={(e) => setDraftSinceTime(e.target.value)}
                    style={{ fontSize: 11, padding: '3px 5px', border: '1px solid #d1d5db', borderRadius: 4, fontFamily: 'inherit', width: 72 }}
                  />
                </div>
              </div>
              <div style={{ fontSize: 11, color: '#374151', display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontWeight: 600 }}>{t('time_to')}</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  <input
                    type="date"
                    value={draftUntilDate}
                    min={draftSinceDate || undefined}
                    onChange={(e) => setDraftUntilDate(e.target.value)}
                    style={{ fontSize: 11, padding: '3px 5px', border: '1px solid #d1d5db', borderRadius: 4, fontFamily: 'inherit', flex: 1 }}
                  />
                  <input
                    type="time"
                    value={draftUntilTime}
                    onChange={(e) => setDraftUntilTime(e.target.value)}
                    style={{ fontSize: 11, padding: '3px 5px', border: '1px solid #d1d5db', borderRadius: 4, fontFamily: 'inherit', width: 72 }}
                  />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', marginTop: 2 }}>
                <button
                  onClick={() => setRangeOpen(false)}
                  style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 999,
                    border: '1px solid #d1d5db', background: 'transparent',
                    color: '#6b7280', cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  {t('cancel')}
                </button>
                <button
                  onClick={applyRange}
                  disabled={!draftSinceDate && !draftUntilDate}
                  style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 999,
                    border: '1px solid #2563eb',
                    background: (!draftSinceDate && !draftUntilDate) ? '#93c5fd' : '#2563eb',
                    color: '#fff', cursor: (!draftSinceDate && !draftUntilDate) ? 'default' : 'pointer',
                    fontFamily: 'inherit', fontWeight: 600,
                  }}
                >
                  {t('apply')}
                </button>
              </div>
              </div>
            </>,
            document.body,
          )}
        </div>

        <Divider />

        {/* Spatial area filter controls */}
        <div style={{ display: 'flex', gap: 5, alignItems: 'center', flexWrap: 'nowrap' }}>
          {!spatialDrawMode && !spatialPolygon && (
            <button
              onClick={() => setSpatialDrawMode(true)}
              title="Bereich auf der Karte zeichnen"
              style={{
                fontSize: 11, padding: '2px 9px', borderRadius: 999,
                border: '1px solid #d1d5db', background: 'transparent',
                color: '#374151', cursor: 'pointer', fontFamily: 'inherit',
                whiteSpace: 'nowrap',
              }}
            >
              ✏ Bereich
            </button>
          )}
          {spatialDrawMode && (
            <>
              <span style={{ fontSize: 11, color: '#3b82f6', fontStyle: 'italic', whiteSpace: 'nowrap' }}>
                Klicken zum Zeichnen…
              </span>
              <button
                onClick={() => setSpatialDrawMode(false)}
                style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 999,
                  border: '1px solid #d1d5db', background: 'transparent',
                  color: '#6b7280', cursor: 'pointer', fontFamily: 'inherit',
                }}
              >
                Abbrechen
              </button>
            </>
          )}
          {spatialPolygon && !spatialDrawMode && (
            <>
              <span style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 999,
                background: '#fffbeb', color: '#b45309',
                border: '1px solid #fcd34d', whiteSpace: 'nowrap',
              }}>
                ◈ Bereich aktiv
              </span>
              <button
                onClick={() => setSpatialPolygon(null)}
                style={{
                  fontSize: 11, padding: '2px 7px', borderRadius: 999,
                  border: '1px solid #d1d5db', background: 'transparent',
                  color: '#6b7280', cursor: 'pointer', fontFamily: 'inherit',
                }}
                title="Bereich entfernen"
              >
                ✕
              </button>
            </>
          )}

          {/* Preset area shortcuts */}
          {!spatialDrawMode && (
            <>
              <Divider />
              {PRESET_AREAS.map((area) => {
                const isActive = area.polygon === null
                  ? spatialPolygon === null
                  : spatialPolygon === area.polygon;
                return (
                  <button
                    key={area.key}
                    onClick={() => setSpatialPolygon(area.polygon)}
                    title={area.key === 'world' ? 'Alle anzeigen' : `Gebiet: ${area.label}`}
                    style={{
                      fontSize: 11, padding: '2px 7px', borderRadius: 999,
                      border: `1px solid ${isActive ? '#f59e0b' : '#d1d5db'}`,
                      background: isActive ? '#fffbeb' : 'transparent',
                      color: isActive ? '#b45309' : '#374151',
                      cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap',
                      fontWeight: isActive ? 600 : 400,
                    }}
                  >
                    {area.label}
                  </button>
                );
              })}
            </>
          )}
        </div>
      </div>

      {/* Row 2: Event type chips */}
      <div style={{ ...row, padding: '3px 12px', borderBottom: '1px solid #f3f4f6' }}>
        <SectionLabel>{t('type')}</SectionLabel>
        <div style={{ marginLeft: 6, flex: 1, overflowX: 'auto', overflowY: 'hidden' }}>
          <EventTypeChips counts={eventTypeTotals} />
        </div>
      </div>

      {/* Row 3: Ansicht · Platforms (conditional) */}
      <div style={{ ...row, padding: '3px 12px', borderBottom: availableLayers.length > 0 ? '1px solid #f3f4f6' : undefined, flexWrap: 'wrap' }}>
        <SectionLabel>{t('view')}</SectionLabel>
        <div style={{ display: 'flex', gap: 10, marginLeft: 6, alignItems: 'center' }}>
          <label style={checkLabel}>
            <input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('show_hidden')}
          </label>
          <label style={checkLabel}>
            <input type="checkbox" checked={showFlagged} onChange={(e) => setShowFlagged(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('show_flagged')}
          </label>
          <label style={checkLabel}>
            <input type="checkbox" checked={showUnflagged} onChange={(e) => setShowUnflagged(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('show_unflagged')}
          </label>
        </div>
        {effectivePlatforms.length > 0 && (
          <>
            <Divider />
            <SectionLabel>{t('platform')}</SectionLabel>
            <div style={{ display: 'flex', gap: 6, marginLeft: 6, alignItems: 'center', flexWrap: 'wrap' }}>
              {effectivePlatforms.map((p) => (
                <label key={p} style={checkLabel}>
                  <input
                    type="checkbox"
                    checked={platforms.length === 0 || platforms.includes(p)}
                    onChange={() => togglePlatform(p)}
                    style={{ width: 12, height: 12 }}
                  />
                  {p}
                  <span style={{ color: '#9ca3af' }}>({fmtCount(platformCounts[p] ?? 0)})</span>
                </label>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Row 4: Layers (conditional) */}
      {availableLayers.length > 0 && (
        <div style={{ ...row, padding: '3px 12px' }}>
          <SectionLabel>{t('layers')}</SectionLabel>
          <div style={{ display: 'flex', gap: 6, marginLeft: 6, alignItems: 'center' }}>
            {availableLayers.map((layer) => {
              const color = getLayerColor(layer.id, availableLayers);
              return (
                <label key={layer.id} style={checkLabel}>
                  <input
                    type="checkbox"
                    checked={activeLayers.includes(layer.id)}
                    onChange={() => toggleLayer(layer.id)}
                    style={{ width: 12, height: 12, accentColor: color }}
                  />
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0, display: 'inline-block' }} />
                  {t('layer_' + layer.name)}
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

