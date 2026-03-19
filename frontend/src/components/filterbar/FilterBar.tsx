import React from 'react';
import { t } from '../../i18n';
import { useFilterStore, ALL_RELEVANCES_LIST } from '../../store/useFilterStore';
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
  } = useFilterStore();

  const { eventTypeTotals } = useReportStore();

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

  return (
    <div
      style={{
        background: '#ffffff',
        borderBottom: '1px solid #e5e7eb',
        height: 48,
        display: 'flex',
        alignItems: 'center',
        paddingLeft: 12,
        paddingRight: 12,
        gap: 0,
        flexShrink: 0,
        fontFamily: "'Inter', system-ui, sans-serif",
        overflow: 'hidden',
      }}
    >
      {/* Location filter */}
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

      {/* Relevance */}
      <SectionLabel>{t('relevance')}</SectionLabel>
      <div style={{ display: 'flex', gap: 4, marginLeft: 6, alignItems: 'center' }}>
        {ALL_RELEVANCES_LIST.map((rel) => {
          const checked = relevances.includes(rel);
          return (
            <label
              key={rel}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                cursor: 'pointer',
                fontSize: 11,
                color: RELEVANCE_COLORS[rel],
                fontWeight: 600,
                whiteSpace: 'nowrap',
              }}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggleRelevance(rel)}
                style={{ accentColor: RELEVANCE_COLORS[rel], width: 12, height: 12 }}
              />
              {t(`rel_${rel}`)}
            </label>
          );
        })}
      </div>

      {effectivePlatforms.length > 0 && (
        <>
          <Divider />
          {/* Platform */}
          <SectionLabel>{t('platform')}</SectionLabel>
          <div style={{ display: 'flex', gap: 4, marginLeft: 6, alignItems: 'center' }}>
            {effectivePlatforms.map((p) => {
              const checked = platforms.length === 0 || platforms.includes(p);
              return (
                <label
                  key={p}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 3,
                    cursor: 'pointer',
                    fontSize: 11,
                    color: '#374151',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => togglePlatform(p)}
                    style={{ width: 12, height: 12 }}
                  />
                  {p}
                </label>
              );
            })}
          </div>
        </>
      )}

      <Divider />

      {/* View */}
      <SectionLabel>{t('view')}</SectionLabel>
      <div style={{ display: 'flex', gap: 8, marginLeft: 6, alignItems: 'center' }}>
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            cursor: 'pointer',
            fontSize: 11,
            color: '#374151',
            whiteSpace: 'nowrap',
          }}
        >
          <input
            type="checkbox"
            checked={showHidden}
            onChange={(e) => setShowHidden(e.target.checked)}
            style={{ width: 12, height: 12 }}
          />
          {t('show_hidden')}
        </label>
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            cursor: 'pointer',
            fontSize: 11,
            color: '#374151',
            whiteSpace: 'nowrap',
          }}
        >
          <input
            type="checkbox"
            checked={showFlagged}
            onChange={(e) => setShowFlagged(e.target.checked)}
            style={{ width: 12, height: 12 }}
          />
          {t('show_flagged')}
        </label>
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            cursor: 'pointer',
            fontSize: 11,
            color: '#374151',
            whiteSpace: 'nowrap',
          }}
        >
          <input
            type="checkbox"
            checked={showUnflagged}
            onChange={(e) => setShowUnflagged(e.target.checked)}
            style={{ width: 12, height: 12 }}
          />
          {t('show_unflagged')}
        </label>
      </div>

      <Divider />

      {/* Event type chips */}
      <SectionLabel>{t('type')}</SectionLabel>
      <div style={{ marginLeft: 6, flex: 1, overflow: 'hidden' }}>
        <EventTypeChips counts={eventTypeTotals} />
      </div>
    </div>
  );
}

// Local type alias to avoid TS error with locFilter
type FilterStore_LocFilter = 'all' | 'localized' | 'pending' | 'unlocalized';
