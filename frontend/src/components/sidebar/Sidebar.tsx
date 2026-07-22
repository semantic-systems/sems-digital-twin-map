import React, { useEffect, useRef, useState } from 'react';
import { t } from '../../i18n';
import { useFilterStore } from '../../store/useFilterStore';
import { useReportStore } from '../../store/useReportStore';
import { useEffectiveFacetTotals } from '../../hooks/useEffectiveFacetTotals';
import { fetchDemoStatus, resetDemo } from '../../api/demo';
import type { DemoStatus } from '../../types';
import { ReportList } from './ReportList';
import { NewPostsBanner } from './NewPostsBanner';

export function Sidebar({ onLoadMore }: { onLoadMore: () => void }): React.ReactElement {
  const { autoUpdate, setAutoUpdate, allPlatforms, setPlatformCounts, search, setSearch, showOnlyNew, setShowOnlyNew, showIssuesView, setShowIssuesView, processingStatusTotals, reportsTotalCount, reportsUnseenCount } = useFilterStore();
  const { isLoading, setReports, setDots, setPendingNewCount, bumpReloadTrigger } = useReportStore();

  // useReportStore's unseenCount/totalCount (surfaced here via useEffectiveFacetTotals
  // for the tour-example adjustment) always describe whichever tab was last fetched,
  // AND optimisticAcknowledge/optimisticHide adjust them instantly on click — so they
  // give live feedback for the tab you're actually looking at. reportsUnseenCount/
  // reportsTotalCount/processingStatusTotals, by contrast, are always computed
  // server-side for BOTH views regardless of which tab is active, but only refresh on
  // the next real fetch (no optimistic updates) — fine for the OTHER, currently-idle
  // tab, but using them for the active tab is what broke live-click feedback. So: live
  // value for the active tab, tab-independent value for the inactive one.
  const { totalCount: activeTabTotal, unseenCount: activeTabUnseen } = useEffectiveFacetTotals();
  const issuesTotal = Object.values(processingStatusTotals).reduce((a, b) => a + b, 0);
  // Issues has no seen/unseen distinction (every matching failure is "actionable"
  // regardless of whether you've looked at it before), so its whole total behaves
  // like "unseen" when it's the inactive side of the combination.
  const otherTabUnseen = showIssuesView ? reportsUnseenCount : issuesTotal;
  const otherTabTotal = showIssuesView ? reportsTotalCount : issuesTotal;
  const combinedUnseen = activeTabUnseen + otherTabUnseen;
  const combinedTotal = activeTabTotal + otherTabTotal;

  // Keep the input responsive on every keystroke, but debounce the store update
  // that drives the refetch so typing "fire" triggers one reload, not four.
  const [searchInput, setSearchInput] = useState(search);
  useEffect(() => {
    if (searchInput === search) return;
    const id = setTimeout(() => setSearch(searchInput), 500);
    return () => clearTimeout(id);
  }, [searchInput, search, setSearch]);

  const [collapsed, setCollapsed] = useState(false);

  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [resetting, setResetting] = useState(false);
  const pollRef = useRef<number | null>(null);

  // Fetch demo status once on mount; if demo_mode, start polling status
  useEffect(() => {
    fetchDemoStatus()
      .then((s) => {
        setDemoStatus(s);
        if (s.demo_mode) startStatusPolling();
      })
      .catch(() => {
        // not in demo mode or endpoint unavailable
      });

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function startStatusPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = window.setInterval(() => {
      fetchDemoStatus()
        .then(setDemoStatus)
        .catch(() => {});
    }, 5_000);
  }

  async function handleReset() {
    setResetting(true);
    try {
      await resetDemo();
      // Clear all local state so the sidebar/map empties immediately
      setReports([], new Date().toISOString(), {});
      setDots([]);
      // Zero out counts but keep the platform list visible
      setPlatformCounts(Object.fromEntries(allPlatforms.map((p) => [p, 0])));
      setPendingNewCount(0);
      bumpReloadTrigger();
      // Refresh demo status
      const s = await fetchDemoStatus();
      setDemoStatus(s);
      startStatusPolling();
    } catch (e) {
      console.error('Demo reset failed:', e);
    } finally {
      setResetting(false);
    }
  }

  const showDemo = demoStatus?.demo_mode === true;

  if (collapsed) {
    return (
      <div
        style={{
          width: 32,
          flexShrink: 0,
          background: '#0f1117',
          borderRight: '1px solid #252836',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 10,
          gap: 8,
          height: '100%',
          fontFamily: "'Inter', system-ui, sans-serif",
          transition: 'width 0.2s',
        }}
      >
        <button
          onClick={() => setCollapsed(false)}
          title="Sidebar öffnen"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#6b7280', fontSize: 16, padding: 2, lineHeight: 1,
          }}
        >
          ›
        </button>
        {combinedUnseen > 0 && (
          <span
            style={{
              background: '#ef4444', color: '#fff', fontSize: 9,
              fontWeight: 700, padding: '1px 4px', borderRadius: 999,
              animation: 'pulse 1.5s ease-in-out infinite',
            }}
          >
            {combinedUnseen}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      data-app-region="sidebar"
      style={{
        width: 380,
        flexShrink: 0,
        background: '#0f1117',
        borderRight: '1px solid #252836',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '10px 12px',
          borderBottom: '1px solid #252836',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={() => setCollapsed(true)}
            title="Sidebar schließen"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: '#4b5563', fontSize: 16, padding: '0 2px 0 0',
              lineHeight: 1, flexShrink: 0,
            }}
          >
            ‹
          </button>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#f0f2f7' }}>
            {t('reports')}
          </span>
          {combinedUnseen > 0 && (
            <span
              style={{
                background: '#ef4444',
                color: '#fff',
                fontSize: 10,
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: 999,
                animation: 'pulse 1.5s ease-in-out infinite',
              }}
            >
              {combinedUnseen}
            </span>
          )}
          <span style={{ fontSize: 11, color: '#4b5563' }}>
            {`(${combinedTotal})`}
          </span>
          {isLoading && (
            <span
              title={t('loading')}
              aria-label={t('loading')}
              role="status"
              style={{
                width: 11,
                height: 11,
                borderRadius: '50%',
                border: '2px solid #374151',
                borderTopColor: '#3b82f6',
                display: 'inline-block',
                animation: 'spin 0.7s linear infinite',
                flexShrink: 0,
              }}
            />
          )}
        </div>

        {/* Right side: auto-update toggle */}
        <label
          data-tour="auto-update-toggle"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            cursor: 'pointer',
            fontSize: 11,
            color: '#9ca3af',
          }}
        >
          <input
            type="checkbox"
            checked={autoUpdate}
            onChange={(e) => setAutoUpdate(e.target.checked)}
            style={{ width: 12, height: 12, accentColor: '#3b82f6' }}
          />
          {t('auto_update')}
          <span style={{ fontSize: 9, color: '#4b5563' }}>({t('recommended')})</span>
        </label>
      </div>

      {/* Tabs: Reports / Issues */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          padding: '6px 10px',
          borderBottom: '1px solid #252836',
          flexShrink: 0,
        }}
      >
        {([
          { key: 'reports', label: t('tab_reports'), active: !showIssuesView, badge: reportsTotalCount },
          { key: 'issues', label: t('tab_issues'), active: showIssuesView, badge: issuesTotal },
        ] as const).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setShowIssuesView(tab.key === 'issues')}
            aria-pressed={tab.active}
            style={{
              flex: 1,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 5,
              padding: '4px 8px',
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 6,
              cursor: 'pointer',
              fontFamily: "'Inter', system-ui, sans-serif",
              border: `1px solid ${tab.active ? '#2563eb' : '#374151'}`,
              background: tab.active ? '#1d4ed8' : 'transparent',
              color: tab.active ? '#fff' : '#9ca3af',
            }}
          >
            {tab.label}
            {tab.badge > 0 && (
              <span
                style={{
                  background: tab.active ? 'rgba(255,255,255,0.25)' : '#ef4444',
                  color: '#fff',
                  fontSize: 9,
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: 999,
                }}
              >
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Demo trickle bar */}
      {showDemo && (
        <div
          style={{
            padding: '7px 12px',
            borderBottom: '1px solid #252836',
            background: '#12151f',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: demoStatus!.running ? 5 : 0,
            }}
          >
            <span style={{ fontSize: 11, color: '#6b7280' }}>
              {demoStatus!.running
                ? `Demo: ${demoStatus!.done} / ${demoStatus!.total} events`
                : demoStatus!.total === 0
                  ? 'Demo ready'
                  : `Demo: ${demoStatus!.done} / ${demoStatus!.total} complete`}
            </span>
            <button
              onClick={handleReset}
              disabled={resetting}
              style={{
                fontSize: 10,
                padding: '2px 8px',
                borderRadius: 4,
                border: '1px solid #374151',
                background: resetting ? '#1f2937' : '#111827',
                color: resetting ? '#4b5563' : '#9ca3af',
                cursor: resetting ? 'default' : 'pointer',
                fontFamily: "'Inter', system-ui, sans-serif",
              }}
            >
              {resetting ? 'Resetting…' : 'Reset demo'}
            </button>
          </div>

          {/* Progress bar */}
          {demoStatus!.total > 0 && (
            <div
              style={{
                height: 3,
                background: '#1f2937',
                borderRadius: 2,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${(demoStatus!.done / demoStatus!.total) * 100}%`,
                  background: demoStatus!.running ? '#3b82f6' : '#22c55e',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Search */}
      <div data-tour="search-box" style={{ padding: '6px 10px', borderBottom: '1px solid #252836', flexShrink: 0 }}>
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder={t('search_reports_ph')}
          style={{
            width: '100%',
            background: '#1a1d27',
            border: '1px solid #374151',
            borderRadius: 6,
            color: '#f0f2f7',
            fontSize: 12,
            padding: '5px 10px',
            fontFamily: "'Inter', system-ui, sans-serif",
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
        <button
          type="button"
          onClick={() => setShowOnlyNew(!showOnlyNew)}
          aria-pressed={showOnlyNew}
          style={{
            marginTop: 6,
            padding: '3px 10px',
            fontSize: 11,
            fontWeight: 600,
            borderRadius: 999,
            cursor: 'pointer',
            fontFamily: "'Inter', system-ui, sans-serif",
            border: `1px solid ${showOnlyNew ? '#2563eb' : '#374151'}`,
            background: showOnlyNew ? '#1d4ed8' : 'transparent',
            color: showOnlyNew ? '#fff' : '#9ca3af',
          }}
        >
          {t('show_only_new')}
        </button>
      </div>

      {/* New posts banner */}
      <NewPostsBanner />

      {/* Report list */}
      <ReportList onLoadMore={onLoadMore} />
    </div>
  );
}
