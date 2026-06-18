import React, { useEffect, useMemo, useRef } from 'react';
import { t } from '../../i18n';
import { useReportStore } from '../../store/useReportStore';
import { useFilterStore } from '../../store/useFilterStore';
import { pointInPolygon } from '../../utils/geo';
import { ReportEntry } from './ReportEntry';

export function ReportList({ onLoadMore }: { onLoadMore: () => void }): React.ReactElement {
  const { reports, activeReportId, hasMore } = useReportStore();
  const { spatialPolygon, locShowLocalized, locShowPending, locShowUnlocalized } = useFilterStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const visibleReports = useMemo(() => {
    let filtered = reports;

    // Location-type filter (frontend — backend always returns all)
    if (!locShowLocalized || !locShowPending || !locShowUnlocalized) {
      filtered = filtered.filter((r) => {
        const locs = r.user_state.locations ?? r.locations;
        const hasCoords = locs.some((l) => l.lat != null && l.lon != null);
        if (hasCoords) return locShowLocalized;
        if (locs.length > 0) return locShowPending;
        return locShowUnlocalized;
      });
    }

    // Spatial polygon filter — Ausstehend/Keine events have no coordinates so they
    // always pass (they can't be spatially disproven, and may well be relevant).
    if (spatialPolygon) {
      filtered = filtered.filter((r) => {
        const locs = r.user_state.locations ?? r.locations;
        const hasCoords = locs.some((l) => l.lat != null && l.lon != null);
        if (!hasCoords) return true;
        return locs.some(
          (l) =>
            l.lat != null &&
            l.lon != null &&
            pointInPolygon(l.lat as number, l.lon as number, spatialPolygon),
        );
      });
    }

    return filtered;
  }, [reports, spatialPolygon, locShowLocalized, locShowPending, locShowUnlocalized]);

  useEffect(() => {
    if (activeReportId === null || !scrollRef.current) return;
    const el = scrollRef.current.querySelector<HTMLElement>(`[data-report-id="${activeReportId}"]`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [activeReportId]);

  if (visibleReports.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#4b5563',
          fontSize: 13,
          fontStyle: 'italic',
          padding: 24,
          fontFamily: "'Inter', system-ui, sans-serif",
        }}
      >
        {t('no_reports')}
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: '6px 8px',
      }}
      className="sidebar-scroll"
    >
      {visibleReports.map((report) => (
        <ReportEntry key={report.id} report={report} />
      ))}
      {hasMore && (
        <div style={{ padding: '8px 4px', textAlign: 'center' }}>
          <button
            onClick={onLoadMore}
            style={{
              background: '#1a1d27',
              border: '1px solid #374151',
              borderRadius: 6,
              color: '#9ca3af',
              fontSize: 12,
              padding: '5px 16px',
              cursor: 'pointer',
              fontFamily: "'Inter', system-ui, sans-serif",
            }}
          >
            {t('load_more')}
          </button>
        </div>
      )}
    </div>
  );
}
