import React, { useEffect, useRef } from 'react';
import { t } from '../../i18n';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { fetchReport } from '../../api/reports';
import { useVisibleReports } from '../../hooks/useVisibleReports';
import { ReportEntry } from './ReportEntry';

export function ReportList({ onLoadMore }: { onLoadMore: () => void }): React.ReactElement {
  const { reports, activeReportId, pinnedReport, setPinnedReport, hasMore } = useReportStore();
  const { username } = useUserStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  // Keep onLoadMore in a ref so the observer effect doesn't re-subscribe every
  // render (App.loadMore is a fresh closure each render).
  const onLoadMoreRef = useRef(onLoadMore);
  onLoadMoreRef.current = onLoadMore;
  // Guards against firing another page load while one is already in flight.
  const loadPendingRef = useRef(false);

  const visibleReports = useVisibleReports();

  // Scroll to top whenever a new pinned card is set.
  useEffect(() => {
    if (pinnedReport) {
      scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [pinnedReport]);

  // Clear the in-flight guard once a page has arrived (reports grew) or there's
  // nothing more to load.
  useEffect(() => {
    loadPendingRef.current = false;
  }, [reports.length, hasMore]);

  // Infinite scroll: auto-load the next page when the bottom sentinel scrolls
  // near the viewport. Re-subscribes when reports grow so a still-visible
  // sentinel keeps paging until the viewport is filled or hasMore is false.
  useEffect(() => {
    const sentinel = sentinelRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root || !hasMore) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loadPendingRef.current) {
          loadPendingRef.current = true;
          onLoadMoreRef.current();
        }
      },
      { root, rootMargin: '300px' },
    );
    obs.observe(sentinel);
    return () => obs.disconnect();
  }, [hasMore, reports.length]);

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
        <div
          ref={sentinelRef}
          style={{
            padding: '10px 4px',
            textAlign: 'center',
            color: '#4b5563',
            fontSize: 11,
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
        >
          {t('loading')}
        </div>
      )}
    </div>
  );
}
