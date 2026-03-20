import React from 'react';
import { t } from '../../i18n';
import { useFilterStore, ALL_RELEVANCES_LIST, getLayerColor } from '../../store/useFilterStore';
import { useReportStore } from '../../store/useReportStore';
import { EventTypeChips } from './EventTypeChips';

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
    locFilter,
    setLocFilter,
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
  } = useFilterStore();

  const { eventTypeTotals, reports } = useReportStore();
  const { platformCounts } = useFilterStore();

  const relevanceCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    for (const r of reports) counts[r.relevance] = (counts[r.relevance] ?? 0) + 1;
    return counts;
  }, [reports]);

  const locOptions: { value: FilterStore_LocFilter; label: string }[] = [
    { value: 'all', label: t('loc_all') },
    { value: 'localized', label: t('loc_located') },
    { value: 'pending', label: t('loc_pending') },
    { value: 'unlocalized', label: t('loc_none') },
  ];

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
    minHeight: 36,
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
      {/* Row 1: Location · Relevance · Platforms */}
      <div style={{ ...row, padding: '4px 12px', borderBottom: '1px solid #f3f4f6' }}>
        <SectionLabel>{t('location')}</SectionLabel>
        <div style={{ display: 'flex', gap: 3, marginLeft: 6 }}>
          {locOptions.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setLocFilter(value)}
              style={{
                fontSize: 11,
                padding: '2px 8px',
                borderRadius: 999,
                border: '1px solid',
                borderColor: locFilter === value ? '#3b82f6' : '#d1d5db',
                background: locFilter === value ? '#3b82f6' : 'transparent',
                color: locFilter === value ? '#fff' : '#374151',
                cursor: 'pointer',
                fontFamily: 'inherit',
                whiteSpace: 'nowrap',
                fontWeight: locFilter === value ? 600 : 400,
                transition: 'all 0.1s',
              }}
            >
              {label}
            </button>
          ))}
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
              {(relevanceCounts[rel] ?? 0) > 0 && (
                <span style={{ color: '#9ca3af', fontWeight: 400 }}>({relevanceCounts[rel]})</span>
              )}
            </label>
          ))}
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
                  <span style={{ color: '#9ca3af' }}>({platformCounts[p] ?? 0})</span>
                </label>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Row 2: View toggles · Event type chips */}
      <div style={{ ...row, padding: '4px 12px' }}>
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

        <SectionLabel>{t('type')}</SectionLabel>
        <div style={{ marginLeft: 6, flex: 1, overflow: 'hidden' }}>
          <EventTypeChips counts={eventTypeTotals} />
        </div>

        {availableLayers.length > 0 && (
          <>
            <Divider />
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
          </>
        )}
      </div>
    </div>
  );
}

// Local type alias to avoid TS error with locFilter
type FilterStore_LocFilter = 'all' | 'localized' | 'pending' | 'unlocalized';
