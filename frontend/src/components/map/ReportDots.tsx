import React from 'react';
import { CircleMarker, Popup } from 'react-leaflet';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { hideReport, flagReport, acknowledgeReport } from '../../api/reports';
import { t } from '../../i18n';
import type { DotDTO } from '../../types';

const RELEVANCE_COLORS: Record<string, string> = {
  high: '#b91c1c',
  medium: '#ea580c',
  low: '#ca8a04',
  none: '#6b7280',
};


interface DotPopupProps {
  dot: DotDTO;
}

function DotPopup({ dot }: DotPopupProps): React.ReactElement {
  const { username } = useUserStore();
  const { optimisticHide, optimisticFlag, reports } = useReportStore();

  const report = reports.find((r) => r.id === dot.report_id);

  const handleHide = async () => {
    if (!username || !report) return;
    const newHide = !report.user_state.hide;
    optimisticHide(dot.report_id, newHide);
    try {
      await hideReport(dot.report_id, username, newHide);
    } catch (e) {
      console.error('Failed to hide from dot:', e);
    }
  };

  const handleFlag = async () => {
    if (!username || !dot.author || !report) return;
    const newFlag = !report.user_state.flag;
    optimisticFlag(dot.author, newFlag);
    try {
      await flagReport(dot.report_id, username, newFlag);
    } catch (e) {
      console.error('Failed to flag from dot:', e);
    }
  };

  const popupBtnStyle: React.CSSProperties = {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 4,
    border: '1px solid #d1d5db',
    background: '#f3f4f6',
    color: '#374151',
    cursor: 'pointer',
    fontFamily: "'Inter', system-ui, sans-serif",
  };

  return (
    <div style={{ maxWidth: 260, fontFamily: "'Inter', system-ui, sans-serif" }}>
      <p style={{ fontSize: 12, color: '#1f2937', marginBottom: 6, lineHeight: 1.4 }}>
        {dot.text.slice(0, 200)}
        {dot.text.length > 200 ? '…' : ''}
      </p>
      {dot.author && (
        <p style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>
          @{dot.author} · {dot.platform}
        </p>
      )}
      <p style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
        {dot.event_type} · {dot.timestamp}
      </p>
      <div style={{ display: 'flex', gap: 4 }}>
        <a
          href={dot.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ ...popupBtnStyle, textDecoration: 'none', display: 'inline-block' }}
        >
          {t('open')}
        </a>
        {report && (
          <>
            <button onClick={handleHide} style={popupBtnStyle}>
              {report.user_state.hide ? t('unhide') : t('hide')}
            </button>
            {dot.author && (
              <button onClick={handleFlag} style={popupBtnStyle}>
                {report.user_state.flag ? t('unflag') : t('flag')}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function ReportDots(): React.ReactElement {
  const { dots, activeReportId, setActiveReportId, optimisticAcknowledge, reports } = useReportStore();
  const { username } = useUserStore();

  return (
    <>
      {dots.map((dot, idx) => {
        const isActive = dot.report_id === activeReportId;
        const color = isActive ? '#3b82f6' : (RELEVANCE_COLORS[dot.relevance] ?? '#6b7280');
        const radius = isActive ? 10 : 7;
        const opacity = dot.seen && !isActive ? 0.35 : 1;

        return (
          <CircleMarker
            key={`${dot.report_id}-${idx}`}
            center={[dot.lat, dot.lon]}
            radius={radius}
            pathOptions={{
              color: color,
              fillColor: color,
              fillOpacity: opacity,
              opacity: opacity,
              weight: isActive ? 2 : 1,
            }}
            eventHandlers={{
              click: () => {
                const newId = isActive ? null : dot.report_id;
                setActiveReportId(newId);
                if (newId !== null && username) {
                  const report = reports.find((r) => r.id === newId);
                  if (report?.user_state.new) {
                    optimisticAcknowledge(newId);
                    acknowledgeReport(newId, username).catch(() => {});
                  }
                }
              },
            }}
          >
            <Popup>
              <DotPopup dot={dot} />
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}
