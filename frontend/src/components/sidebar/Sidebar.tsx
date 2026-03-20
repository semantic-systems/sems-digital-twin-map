import React, { useEffect, useRef, useState } from 'react';
import { t } from '../../i18n';
import { useFilterStore } from '../../store/useFilterStore';
import { useReportStore } from '../../store/useReportStore';
import { fetchDemoStatus, resetDemo } from '../../api/demo';
import type { DemoStatus } from '../../types';
import { ReportList } from './ReportList';
import { NewPostsBanner } from './NewPostsBanner';

export function Sidebar(): React.ReactElement {
  const { autoUpdate, setAutoUpdate, allPlatforms, setPlatformCounts } = useFilterStore();
  const { reports, setReports, setDots, setPendingNewCount, bumpReloadTrigger } = useReportStore();
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

  // Count unseen high/medium reports for the notification badge
  const unseenCount = reports.filter(
    (r) =>
      !r.user_state.hide &&
      r.user_state.new &&
      (r.relevance === 'high' || r.relevance === 'medium'),
  ).length;

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
        {unseenCount > 0 && (
          <span
            style={{
              background: '#ef4444', color: '#fff', fontSize: 9,
              fontWeight: 700, padding: '1px 4px', borderRadius: 999,
              animation: 'pulse 1.5s ease-in-out infinite',
            }}
          >
            {unseenCount}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
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
          {unseenCount > 0 && (
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
              {unseenCount}
            </span>
          )}
          <span style={{ fontSize: 11, color: '#4b5563' }}>
            ({reports.length})
          </span>
        </div>

        {/* Right side: auto-update toggle */}
        <label
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
        </label>
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

      {/* New posts banner */}
      <NewPostsBanner />

      {/* Report list */}
      <ReportList />
    </div>
  );
}
