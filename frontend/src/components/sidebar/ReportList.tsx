import React, { useEffect, useRef } from 'react';
import { t } from '../../i18n';
import { useReportStore } from '../../store/useReportStore';
import { ReportEntry } from './ReportEntry';

export function ReportList(): React.ReactElement {
  const { reports, activeReportId } = useReportStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeReportId === null || !scrollRef.current) return;
    const el = scrollRef.current.querySelector<HTMLElement>(`[data-report-id="${activeReportId}"]`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [activeReportId]);

  if (reports.length === 0) {
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
      {reports.map((report) => (
        <ReportEntry key={report.id} report={report} />
      ))}
    </div>
  );
}
