import React, { useEffect, useMemo, useRef } from 'react';
import { t } from '../../i18n';
import { useReportStore } from '../../store/useReportStore';
import { useFilterStore } from '../../store/useFilterStore';
import { pointInPolygon } from '../../utils/geo';
import { ReportEntry } from './ReportEntry';

export function ReportList({ onLoadMore }: { onLoadMore: () => void }): React.ReactElement {
  const { reports, activeReportId, hasMore } = useReportStore();
  const { spatialPolygon } = useFilterStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const visibleReports = useMemo(() => {
    if (!spatialPolygon) return reports;
    return reports.filter((r) => {
      const locs = r.user_state.locations ?? r.locations;
      return locs.some(
        (loc) =>
          loc.lat != null &&
          loc.lon != null &&
          pointInPolygon(loc.lat as number, loc.lon as number, spatialPolygon),
      );
    });
  }, [reports, spatialPolygon]);

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
