import React from 'react';
import { t } from '../../i18n';
import type { LocationEntry } from '../../types';
import { useMapStore } from '../../store/useMapStore';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { updateLocations } from '../../api/reports';

interface LocationTagProps {
  loc: LocationEntry;
  reportId: number;
  locIndex: number;
  allLocations: LocationEntry[];
}

export function LocationTag({
  loc,
  reportId,
  locIndex,
  allLocations,
}: LocationTagProps): React.ReactElement {
  const { enterPickMode } = useMapStore();
  const { optimisticUpdateLocations } = useReportStore();
  const { username } = useUserStore();

  const isGeo = Boolean(loc.osm_id);
  const displayName = loc.mention || loc.name || (loc.lat ? `${loc.lat?.toFixed(4)}, ${loc.lon?.toFixed(4)}` : '?');

  const handleReassign = () => {
    enterPickMode(reportId, locIndex, loc.mention ?? null);
  };

  const handleRemove = async () => {
    if (!username) return;
    const newLocs = allLocations.filter((_, i) => i !== locIndex);
    optimisticUpdateLocations(reportId, newLocs);
    try {
      await updateLocations(reportId, username, newLocs);
    } catch (e) {
      console.error('Failed to remove location:', e);
      // revert
      optimisticUpdateLocations(reportId, allLocations);
    }
  };

  if (isGeo) {
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 2,
          background: '#14532d',
          border: '1px solid #166534',
          borderRadius: 4,
          padding: '1px 5px',
          fontSize: 10,
          color: '#86efac',
          whiteSpace: 'nowrap',
          maxWidth: 180,
        }}
      >
        <button
          title={t('reassign_title')}
          onClick={handleReassign}
          style={{
            background: 'none',
            border: 'none',
            padding: 0,
            cursor: 'pointer',
            color: '#86efac',
            fontSize: 10,
            fontStyle: 'italic',
            textDecoration: 'underline dotted',
            textDecorationColor: '#4ade80',
            maxWidth: 130,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
        >
          {displayName}
        </button>
        <button
          title={t('remove_location')}
          onClick={handleRemove}
          style={{
            background: 'none',
            border: 'none',
            padding: '0 2px',
            cursor: 'pointer',
            color: '#4ade80',
            fontSize: 10,
            lineHeight: 1,
            opacity: 0.7,
          }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = '1')}
          onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = '0.7')}
        >
          ✕
        </button>
      </span>
    );
  }

  // Pending (no osm_id)
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 2,
        border: '1px dashed #f97316',
        borderRadius: 4,
        padding: '1px 5px',
        fontSize: 10,
        color: '#fdba74',
        whiteSpace: 'nowrap',
        maxWidth: 180,
      }}
    >
      <button
        title={t('georeference_title')}
        onClick={handleReassign}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          color: '#fdba74',
          fontSize: 10,
          fontStyle: 'italic',
          textDecoration: 'underline dotted',
          textDecorationColor: '#f97316',
          maxWidth: 130,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          fontFamily: "'Inter', system-ui, sans-serif",
        }}
      >
        {displayName}
      </button>
      <button
        title={t('remove_location')}
        onClick={handleRemove}
        style={{
          background: 'none',
          border: 'none',
          padding: '0 2px',
          cursor: 'pointer',
          color: '#fb923c',
          fontSize: 10,
          lineHeight: 1,
          opacity: 0.7,
        }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = '1')}
        onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = '0.7')}
      >
        ✕
      </button>
    </span>
  );
}
