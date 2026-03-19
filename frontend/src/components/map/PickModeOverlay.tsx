import React, { useState } from 'react';
import { t } from '../../i18n';
import { useMapStore } from '../../store/useMapStore';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { updateLocations, fetchDots } from '../../api/reports';
import { useFilterStore } from '../../store/useFilterStore';
import type { NominatimResult, LocationEntry } from '../../types';

const BASE_API = '/api/v1';

export function PickModeOverlay(): React.ReactElement | null {
  const { pickMode, exitPickMode } = useMapStore();
  const { reports, optimisticUpdateLocations, setDots } = useReportStore();
  const { username } = useUserStore();
  const filters = useFilterStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<NominatimResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [noResults, setNoResults] = useState(false);

  if (!pickMode) return null;

  const { mention } = pickMode;

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setNoResults(false);
    setResults([]);
    try {
      const res = await fetch(
        `${BASE_API}/geo/nominatim?q=${encodeURIComponent(searchQuery.trim())}`,
      );
      if (!res.ok) throw new Error('nominatim error');
      const data: NominatimResult[] = await res.json();
      if (data.length === 0) setNoResults(true);
      setResults(data);
    } catch (e) {
      console.error('Nominatim search failed:', e);
      setNoResults(true);
    } finally {
      setSearching(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleResultClick = async (result: NominatimResult) => {
    if (!username) return;
    const report = reports.find((r) => r.id === pickMode.reportId);
    if (!report) return;

    const effectiveLocs: LocationEntry[] =
      report.user_state.locations !== undefined && report.user_state.locations !== null
        ? report.user_state.locations
        : [...report.locations];

    const newLoc: LocationEntry = {
      mention: mention ?? result.display_name,
      name: result.display_name,
      lat: parseFloat(result.lat),
      lon: parseFloat(result.lon),
      osm_id: result.osm_id ? String(result.osm_id) : undefined,
      osm_type: result.osm_type,
      display_name: result.display_name,
      boundingbox: result.boundingbox
        ? result.boundingbox.map(Number)
        : undefined,
      polygon: result.geojson,
    };

    let newLocs: LocationEntry[];
    if (pickMode.locIndex !== null) {
      newLocs = effectiveLocs.map((l, i) => (i === pickMode.locIndex ? newLoc : l));
    } else {
      newLocs = [...effectiveLocs, newLoc];
    }

    optimisticUpdateLocations(pickMode.reportId, newLocs);
    exitPickMode();
    setResults([]);
    setSearchQuery('');

    try {
      await updateLocations(pickMode.reportId, username, newLocs);
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
      console.error('Failed to update locations via search:', e);
    }
  };

  const overlayInstruction = mention
    ? `${t('pick_prompt')} "${mention}"`
    : t('pick_prompt');

  return (
    <div
      style={{
        position: 'fixed',
        top: 60,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 1000,
        background: '#2563eb',
        color: '#fff',
        borderRadius: 8,
        padding: '10px 16px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
        minWidth: 340,
        maxWidth: 440,
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
    >
      {/* Instruction */}
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>
        {overlayInstruction}
      </div>

      {/* Cancel button */}
      <button
        onClick={() => {
          exitPickMode();
          setResults([]);
          setSearchQuery('');
        }}
        style={{
          position: 'absolute',
          top: 8,
          right: 10,
          background: 'rgba(255,255,255,0.15)',
          border: 'none',
          color: '#fff',
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 4,
          cursor: 'pointer',
          fontFamily: 'inherit',
        }}
      >
        {t('cancel')}
      </button>

      {/* Divider */}
      <div
        style={{
          fontSize: 11,
          textAlign: 'center',
          color: 'rgba(255,255,255,0.6)',
          marginBottom: 8,
        }}
      >
        {t('or')}
      </div>

      {/* Search row */}
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleKey}
          placeholder={t('search_osm_ph')}
          style={{
            flex: 1,
            padding: '6px 10px',
            fontSize: 12,
            border: '1px solid rgba(255,255,255,0.3)',
            borderRadius: 6,
            background: 'rgba(255,255,255,0.15)',
            color: '#fff',
            outline: 'none',
            fontFamily: 'inherit',
          }}
        />
        <button
          onClick={handleSearch}
          disabled={searching}
          style={{
            padding: '6px 12px',
            fontSize: 12,
            background: '#fff',
            color: '#2563eb',
            border: 'none',
            borderRadius: 6,
            cursor: searching ? 'not-allowed' : 'pointer',
            fontWeight: 600,
            fontFamily: 'inherit',
          }}
        >
          {searching ? '…' : '🔍'}
        </button>
      </div>

      {/* Results */}
      {noResults && (
        <div
          style={{
            marginTop: 8,
            fontSize: 12,
            color: 'rgba(255,255,255,0.7)',
            fontStyle: 'italic',
          }}
        >
          {t('no_results')}
        </div>
      )}
      {results.length > 0 && (
        <div
          style={{
            marginTop: 8,
            background: '#fff',
            borderRadius: 6,
            maxHeight: 240,
            overflowY: 'auto',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
          }}
        >
          {results.map((r) => (
            <button
              key={r.place_id}
              onClick={() => handleResultClick(r)}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 12px',
                textAlign: 'left',
                background: 'none',
                border: 'none',
                borderBottom: '1px solid #e5e7eb',
                cursor: 'pointer',
                fontSize: 12,
                color: '#1f2937',
                fontFamily: 'inherit',
                lineHeight: 1.4,
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = '#eff6ff';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = 'none';
              }}
            >
              {r.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
