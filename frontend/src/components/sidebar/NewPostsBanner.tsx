import React from 'react';
import { newPostsLabel } from '../../i18n';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { useFilterStore } from '../../store/useFilterStore';
import { admitAllReports, fetchReports, fetchDots } from '../../api/reports';

export function NewPostsBanner(): React.ReactElement {
  const { pendingNewCount, setPendingNewCount, setReports, setDots } = useReportStore();
  const { username } = useUserStore();
  const filters = useFilterStore();
  const { setAllPlatforms, setPlatformCounts, setPlatformAddedCounts } = filters;

  const handleClick = async () => {
    if (!username || pendingNewCount === 0) return;

    try {
      const effectivePlatforms = filters.platforms.length ? filters.platforms : filters.allPlatforms;
      const params = {
        username,
        loc_filter: filters.locFilter,
        platforms: effectivePlatforms,
        event_types: filters.eventTypes,
        relevances: filters.relevances,
        show_hidden: filters.showHidden,
        show_flagged: filters.showFlagged,
        show_unflagged: filters.showUnflagged,
      };

      // Admit only filter-matching pending reports
      await admitAllReports(username, {
        platforms: effectivePlatforms,
        event_types: filters.eventTypes,
        relevances: filters.relevances,
      });
      const reloaded = await fetchReports(params);
      setReports(reloaded.reports, reloaded.loaded_at, reloaded.event_type_totals, reloaded.relevance_totals);
      if (reloaded.all_platforms?.length) setAllPlatforms(reloaded.all_platforms);
      if (reloaded.platform_counts) setPlatformCounts(reloaded.platform_counts);
      if (reloaded.platform_added_counts) setPlatformAddedCounts(reloaded.platform_added_counts);
      const dotsRes = await fetchDots(params);
      setDots(dotsRes.dots);
      setPendingNewCount(0);
    } catch (e) {
      console.error('Failed to admit reports:', e);
    }
  };

  const active = pendingNewCount > 0;

  return (
    <button
      onClick={handleClick}
      disabled={!active}
      style={{
        width: '100%',
        padding: '7px 12px',
        background: active ? '#2563eb' : '#1e2235',
        color: active ? '#fff' : '#4b5563',
        border: 'none',
        borderBottom: '1px solid #252836',
        cursor: active ? 'pointer' : 'default',
        fontSize: 12,
        fontWeight: active ? 600 : 400,
        fontFamily: "'Inter', system-ui, sans-serif",
        textAlign: 'center',
        transition: 'background 0.15s',
        flexShrink: 0,
      }}
      onMouseEnter={(e) => {
        if (active)
          (e.currentTarget as HTMLButtonElement).style.background = '#1d4ed8';
      }}
      onMouseLeave={(e) => {
        if (active)
          (e.currentTarget as HTMLButtonElement).style.background = '#2563eb';
      }}
    >
      {newPostsLabel(pendingNewCount)}
    </button>
  );
}
