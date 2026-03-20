import React from 'react';
import { t } from '../../i18n';
import type { ReportDTO, LocationEntry } from '../../types';
import { useReportStore } from '../../store/useReportStore';
import { useMapStore } from '../../store/useMapStore';
import { useUserStore } from '../../store/useUserStore';
import { hideReport, flagReport, acknowledgeReport, restoreLocations, fetchDots } from '../../api/reports';
import { useFilterStore } from '../../store/useFilterStore';
import { LocationTag } from './LocationTag';

interface ReportEntryProps {
  report: ReportDTO;
}

const RELEVANCE_RIGHT_BORDER: Record<string, string> = {
  high: '#b91c1c',
  medium: '#ea580c',
  low: '#ca8a04',
  none: '#6b7280',
};

function getGeoIcon(locations: LocationEntry[]): { icon: string; title: string } {
  if (locations.some((l) => l.osm_id)) return { icon: '📍', title: t('geo_title') };
  if (locations.length > 0) return { icon: '◎', title: t('pending_title') };
  return { icon: '·', title: t('no_loc_title') };
}

function getLeftBorderColor(locations: LocationEntry[]): string {
  if (locations.some((l) => l.osm_id)) return '#22c55e';
  if (locations.length > 0) return '#f97316';
  return '#374151';
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatPlatform(platform: string): string {
  if (platform.startsWith('rss')) {
    const parts = platform.split('/');
    return parts.length > 1 ? parts.slice(1).join('/') : platform;
  }
  return platform;
}

export function ReportEntry({ report }: ReportEntryProps): React.ReactElement {
  const { activeReportId, setActiveReportId, optimisticHide, optimisticFlag, optimisticAcknowledge, optimisticRestoreLocations, setDots } =
    useReportStore();
  const { enterPickMode, requestFitBounds } = useMapStore();
  const { username } = useUserStore();
  const filters = useFilterStore();

  const isActive = activeReportId === report.id;
  const { hide, flag, new: isNew, locations: userLocations } = report.user_state;

  // Use user-modified locations if available, otherwise use server locations
  const effectiveLocations: LocationEntry[] =
    userLocations !== undefined && userLocations !== null ? userLocations : report.locations;

  const hasGeoref = effectiveLocations.some((l) => l.osm_id);
  const hasPending = !hasGeoref && effectiveLocations.length > 0;
  // Center is only useful when there are actual coordinates to pan to
  const hasCoords = effectiveLocations.some(
    (l) => (l.osm_id && l.boundingbox) || (l.lat != null && l.lon != null),
  );
  const geoInfo = getGeoIcon(effectiveLocations);
  const leftBorder = getLeftBorderColor(effectiveLocations);
  const rightBorder = RELEVANCE_RIGHT_BORDER[report.relevance] ?? '#6b7280';

  const handleTextClick = async () => {
    const newId = isActive ? null : report.id;
    setActiveReportId(newId);
    if (newId !== null && isNew && username) {
      optimisticAcknowledge(newId);
      try {
        await acknowledgeReport(newId, username);
      } catch (e) {
        console.error('Failed to acknowledge:', e);
      }
    }
  };

  const handleCenter = () => {
    const georef = effectiveLocations.find((l) => l.osm_id && l.boundingbox);
    if (georef?.boundingbox) {
      const bb = georef.boundingbox;
      // boundingbox: [south, north, west, east]
      requestFitBounds([
        [Number(bb[0]), Number(bb[2])],
        [Number(bb[1]), Number(bb[3])],
      ]);
    } else {
      const withCoords = effectiveLocations.find((l) => l.lat && l.lon);
      if (withCoords) {
        const lat = Number(withCoords.lat);
        const lon = Number(withCoords.lon);
        requestFitBounds([
          [lat - 0.01, lon - 0.01],
          [lat + 0.01, lon + 0.01],
        ]);
      }
    }
  };

  const handleHide = async () => {
    if (!username) return;
    const newHide = !hide;
    optimisticHide(report.id, newHide);
    try {
      await hideReport(report.id, username, newHide);
    } catch (e) {
      console.error('Failed to hide:', e);
      optimisticHide(report.id, hide);
    }
  };

  const handleFlag = async () => {
    if (!username || !report.author) return;
    const newFlag = !flag;
    optimisticFlag(report.author, newFlag);
    try {
      await flagReport(report.id, username, newFlag);
    } catch (e) {
      console.error('Failed to flag:', e);
      optimisticFlag(report.author, flag);
    }
  };

  const handleAddLocation = () => {
    enterPickMode(report.id, null, null);
  };

  const handleRestore = async () => {
    if (!username) return;
    optimisticRestoreLocations(report.id, report.original_locations);
    try {
      await restoreLocations(report.id, username);
      const dotsRes = await fetchDots({
        username,
        loc_filter: filters.locFilter,
        platforms: filters.platforms.length ? filters.platforms : filters.allPlatforms,
        event_types: filters.eventTypes,
        relevances: filters.relevances,
        show_hidden: filters.showHidden,
        show_flagged: filters.showFlagged,
        show_unflagged: filters.showUnflagged,
      });
      setDots(dotsRes.dots);
    } catch (e) {
      console.error('Failed to restore locations:', e);
    }
  };

  const cardStyle: React.CSSProperties = {
    background: isActive ? '#0f2044' : '#181b23',
    borderRadius: 6,
    padding: '8px 8px 6px 10px',
    marginBottom: 6,
    borderLeft: `4px solid ${isActive ? '#3b82f6' : leftBorder}`,
    borderRight: `3px solid ${rightBorder}`,
    borderTop: isActive ? '1px solid #1d4ed8' : '1px solid #252836',
    borderBottom: isActive ? '1px solid #1d4ed8' : '1px solid #252836',
    opacity: hide ? 0.45 : 1,
    outline: flag ? '2px solid #f97316' : isActive ? '1px solid #2563eb' : 'none',
    outlineOffset: -1,
    boxShadow: isActive ? '0 0 0 1px #1d4ed8 inset' : 'none',
    transition: 'opacity 0.2s, background 0.15s',
    position: 'relative',
    cursor: 'default',
  };

  const btnBase: React.CSSProperties = {
    fontSize: 11,
    padding: '2px 7px',
    borderRadius: 4,
    border: '1px solid #252836',
    background: '#252836',
    color: '#9ca3af',
    cursor: 'pointer',
    fontFamily: "'Inter', system-ui, sans-serif",
    whiteSpace: 'nowrap',
    transition: 'background 0.1s, color 0.1s',
  };

  const metaLine = [
    geoInfo.icon,
    report.author ? `@${report.author}` : null,
    formatPlatform(report.platform),
    report.event_type,
    t(`rel_${report.relevance}`),
    formatTimestamp(report.timestamp),
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <div style={cardStyle} className={isActive ? 'report-entry-active' : undefined} data-report-id={report.id}>
      {/* NEW badge */}
      {isNew && (
        <span
          style={{
            display: 'inline-block',
            background: '#ef4444',
            color: '#fff',
            fontSize: 9,
            fontWeight: 700,
            padding: '1px 5px',
            borderRadius: 999,
            marginBottom: 4,
            letterSpacing: '0.05em',
          }}
        >
          {t('new_badge')}
        </span>
      )}

      {/* Text button */}
      <button
        onClick={handleTextClick}
        style={{
          display: 'block',
          width: '100%',
          background: 'none',
          border: 'none',
          padding: 0,
          textAlign: 'left',
          cursor: 'pointer',
          color: '#f0f2f7',
        }}
      >
        <p
          className="report-text-clamp"
          style={{
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 1.5,
            color: '#f0f2f7',
            fontFamily: "'Inter', system-ui, sans-serif",
            marginBottom: 3,
          }}
        >
          {report.text}
        </p>
        <p
          style={{
            fontSize: 11,
            color: '#6b7280',
            fontFamily: "'Inter', system-ui, sans-serif",
            lineHeight: 1.5,
            whiteSpace: 'normal',
          }}
          title={geoInfo.title}
        >
          {metaLine}
        </p>
      </button>

      {/* Action row */}
      <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
        <a
          href={report.url}
          target="_blank"
          rel="noopener noreferrer"
          title={t('open_title')}
          style={{
            ...btnBase,
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLAnchorElement).style.background = '#374151';
            (e.currentTarget as HTMLAnchorElement).style.color = '#f0f2f7';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLAnchorElement).style.background = '#252836';
            (e.currentTarget as HTMLAnchorElement).style.color = '#9ca3af';
          }}
        >
          {t('open')}
        </a>

        <button
          onClick={handleCenter}
          disabled={!hasCoords}
          title={t('center_title')}
          style={{
            ...btnBase,
            opacity: hasCoords ? 1 : 0.4,
            cursor: hasCoords ? 'pointer' : 'not-allowed',
          }}
          onMouseEnter={(e) => {
            if (hasCoords) {
              (e.currentTarget as HTMLButtonElement).style.background = '#374151';
              (e.currentTarget as HTMLButtonElement).style.color = '#f0f2f7';
            }
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = '#252836';
            (e.currentTarget as HTMLButtonElement).style.color = '#9ca3af';
          }}
        >
          {t('center')}
        </button>

        <button
          onClick={handleHide}
          title={hide ? t('unhide') : t('hide')}
          style={btnBase}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = '#374151';
            (e.currentTarget as HTMLButtonElement).style.color = '#f0f2f7';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = '#252836';
            (e.currentTarget as HTMLButtonElement).style.color = '#9ca3af';
          }}
        >
          {hide ? t('unhide') : t('hide')}
        </button>

        <button
          onClick={handleFlag}
          disabled={!report.author}
          title={
            !report.author
              ? t('no_author_title')
              : flag
                ? t('unflag_title')
                : t('flag_title')
          }
          style={{
            ...btnBase,
            color: flag ? '#f97316' : '#9ca3af',
            borderColor: flag ? '#f97316' : '#252836',
            opacity: report.author ? 1 : 0.4,
            cursor: report.author ? 'pointer' : 'not-allowed',
          }}
          onMouseEnter={(e) => {
            if (report.author) {
              (e.currentTarget as HTMLButtonElement).style.background = '#374151';
            }
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = '#252836';
          }}
        >
          {flag ? t('unflag') : t('flag')}
        </button>
      </div>

      {/* Location tags */}
      {effectiveLocations.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 5 }}>
          {effectiveLocations.map((loc, i) => (
            <LocationTag
              key={i}
              loc={loc}
              reportId={report.id}
              locIndex={i}
              allLocations={effectiveLocations}
            />
          ))}
        </div>
      )}

      {/* Add location button */}
      <div style={{ display: 'flex', gap: 4, marginTop: 5, flexWrap: 'wrap' }}>
        <button
          onClick={handleAddLocation}
          title={t('add_location_title')}
          style={{
            fontSize: 10,
            padding: '2px 7px',
            borderRadius: 999,
            border: '1px solid #1d4ed8',
            background: '#1e3a8a',
            color: '#93c5fd',
            cursor: 'pointer',
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = '#1d4ed8';
            (e.currentTarget as HTMLButtonElement).style.color = '#fff';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = '#1e3a8a';
            (e.currentTarget as HTMLButtonElement).style.color = '#93c5fd';
          }}
        >
          {t('add_location')}
        </button>

        {/* Restore button — only if user has modified locations */}
        {userLocations !== undefined && userLocations !== null && (
          <button
            onClick={handleRestore}
            title={t('restore_title')}
            style={{
              fontSize: 10,
              padding: '2px 7px',
              borderRadius: 999,
              border: '1px solid #6d28d9',
              background: '#4c1d95',
              color: '#c4b5fd',
              cursor: 'pointer',
              fontFamily: "'Inter', system-ui, sans-serif",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = '#6d28d9';
              (e.currentTarget as HTMLButtonElement).style.color = '#fff';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = '#4c1d95';
              (e.currentTarget as HTMLButtonElement).style.color = '#c4b5fd';
            }}
          >
            {t('restore_locations')}
          </button>
        )}
      </div>
    </div>
  );
}
