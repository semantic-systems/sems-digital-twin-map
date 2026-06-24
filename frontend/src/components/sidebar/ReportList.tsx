import React, { useEffect, useMemo, useRef } from 'react';
import { t } from '../../i18n';
import { useReportStore } from '../../store/useReportStore';
import { useFilterStore } from '../../store/useFilterStore';
import { useUserStore } from '../../store/useUserStore';
import { fetchReport } from '../../api/reports';
import { pointInPolygon } from '../../utils/geo';
import { ReportEntry } from './ReportEntry';

export function ReportList({ onLoadMore }: { onLoadMore: () => void }): React.ReactElement {
  const { reports, activeReportId, pinnedReport, setPinnedReport, hasMore } = useReportStore();
  const { spatialPolygon } = useFilterStore();
  const { username } = useUserStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const visibleReports = useMemo(() => {
    let filtered = reports;

    // Spatial polygon filter — reports with no coordinates always pass
    // (they can't be spatially disproven, and may well be relevant).
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

  // Scroll to top whenever a new pinned card is set.
  useEffect(() => {
    if (pinnedReport) {
      scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [pinnedReport]);

  // When a report is selected, scroll to it if it's in the loaded page; otherwise
  // fetch it on demand and pin it at the top (avoids paging through history).
  useEffect(() => {
    if (activeReportId === null) {
      setPinnedReport(null);
      return;
    }

    // Already in the loaded list → scroll to it, clear any stale pin.
    if (reports.some((r) => r.id === activeReportId)) {
      setPinnedReport(null);
      const el = scrollRef.current?.querySelector<HTMLElement>(`[data-report-id="${activeReportId}"]`);
      el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      return;
    }

    // Already pinned this one → nothing to do.
    if (pinnedReport?.id === activeReportId) return;

    // Not in the loaded page → fetch it directly and pin it.
    let cancelled = false;
    fetchReport(activeReportId, username ?? undefined)
      .then((r) => { if (!cancelled) setPinnedReport(r); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [activeReportId, reports, username, pinnedReport, setPinnedReport]);

  // Show the pinned card only when it isn't already part of the loaded/visible list.
  const pinnedToShow =
    pinnedReport && !visibleReports.some((r) => r.id === pinnedReport.id)
      ? pinnedReport
      : null;

  if (visibleReports.length === 0 && !pinnedToShow) {
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
      {pinnedToShow && <ReportEntry key={`pinned-${pinnedToShow.id}`} report={pinnedToShow} pinned />}
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
