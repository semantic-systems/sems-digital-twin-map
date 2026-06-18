import React from 'react';
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
    activeLayers,
    availableLayers,
    toggleLayer,
    spatialPolygon,
    spatialDrawMode,
    setSpatialPolygon,
    setSpatialDrawMode,
  } = useFilterStore();

  const { eventTypeTotals, relevanceTotals } = useReportStore();
  const { platformCounts } = useFilterStore();

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
      <div style={{ ...row, padding: '4px 12px', borderBottom: '1px solid #f3f4f6' }}>
        <SectionLabel>{t('location')}</SectionLabel>
        <div style={{ display: 'flex', gap: 10, marginLeft: 6, alignItems: 'center' }}>
          <label style={checkLabel}>
            <input type="checkbox" checked={locShowLocalized} onChange={(e) => setLocShowLocalized(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('loc_located')}
          </label>
          <label style={checkLabel}>
            <input type="checkbox" checked={locShowPending} onChange={(e) => setLocShowPending(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('loc_pending')}
          </label>
          <label style={checkLabel}>
            <input type="checkbox" checked={locShowUnlocalized} onChange={(e) => setLocShowUnlocalized(e.target.checked)} style={{ width: 12, height: 12 }} />
            {t('loc_none')}
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
                <span style={{ color: '#9ca3af', fontWeight: 400 }}>({relevanceTotals[rel]})</span>
              )}
            </label>
          ))}
        </div>

        <Divider />

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

      {/* Row 3: Platforms (conditional) */}
      {effectivePlatforms.length > 0 && (
        <div style={{ ...row, padding: '3px 12px', borderBottom: availableLayers.length > 0 ? '1px solid #f3f4f6' : undefined, flexWrap: 'wrap' }}>
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
                <span style={{ color: '#9ca3af' }}>({platformCounts[p] ?? 0})</span>
              </label>
            ))}
          </div>
        </div>
      )}

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

