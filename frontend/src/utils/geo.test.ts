import { describe, it, expect } from 'vitest';
import {
  locationExtent,
  computeSuppressedRegions,
  computeSuppressedDotsWithLocs,
  filterLocationsWithVisibleDots,
  computeVisibleReportBounds,
  dedupByOsm,
  osmKey,
} from './geo';
import type { LocationEntry, DotDTO } from '../types';

function makeDot(overrides: Partial<DotDTO> = {}): DotDTO {
  return {
    report_id: 1,
    lat: 0,
    lon: 0,
    seen: false,
    hide: false,
    flag: false,
    new: false,
    location_name: '',
    location_display: '',
    text: '',
    author: '',
    platform: 'mastodon',
    timestamp: '2026-01-01T00:00:00Z',
    event_types: [],
    relevance: 'high',
    url: '',
    ...overrides,
  };
}

describe('locationExtent', () => {
  it('computes the bbox over the WHOLE polygon geometry, not just the first ring', () => {
    // Regression test for the exact bug found in production: a district polygon
    // whose first ring was a tiny unrepresentative fragment, while the true
    // extent (spanning all rings) was much larger. Using only ring[0] would
    // shrink this to a sliver and defeat containment suppression.
    const outer: [number, number][] = [[10, 50], [11, 50], [11, 51], [10, 51], [10, 50]];
    const holeFarAway: [number, number][] = [[20, 60], [21, 60], [21, 61], [20, 61], [20, 60]];
    const loc: LocationEntry = {
      osm_id: '1', osm_type: 'relation',
      polygon: { type: 'Polygon', coordinates: [outer, holeFarAway] },
    };
    expect(locationExtent(loc)).toEqual([50, 61, 10, 21]);
  });

  it('computes the bbox across every polygon of a MultiPolygon', () => {
    const loc: LocationEntry = {
      osm_id: '1', osm_type: 'relation',
      polygon: {
        type: 'MultiPolygon',
        coordinates: [
          [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
          [[[5, 5], [6, 5], [6, 6], [5, 6], [5, 5]]],
        ],
      },
    };
    expect(locationExtent(loc)).toEqual([0, 6, 0, 6]);
  });

  it('skips Point geometries (unreliable stored coordinate order)', () => {
    const loc: LocationEntry = {
      osm_id: '1', osm_type: 'node',
      polygon: { type: 'Point', coordinates: [10, 50] },
      lat: 50, lon: 10,
    };
    // Falls through to the lat/lon fallback, not the (untrusted) Point geometry.
    expect(locationExtent(loc)).toEqual([50, 50, 10, 10]);
  });

  it('falls back to the Nominatim boundingbox when there is no polygon', () => {
    const loc: LocationEntry = { boundingbox: [50, 51, 10, 11] as unknown as number[] };
    expect(locationExtent(loc)).toEqual([50, 51, 10, 11]);
  });

  it('falls back to a degenerate point extent when only lat/lon is known', () => {
    const loc: LocationEntry = { lat: 50, lon: 10 };
    expect(locationExtent(loc)).toEqual([50, 50, 10, 10]);
  });

  it('returns null when there is nothing to derive an extent from', () => {
    expect(locationExtent({})).toBeNull();
  });
});

describe('computeSuppressedRegions', () => {
  it('suppresses a region whose box strictly contains another', () => {
    const district: [number, number, number, number] = [47.6, 48.2, 12.3, 12.9];
    const town: [number, number, number, number] = [47.83, 47.94, 12.58, 12.70];
    const suppressed = computeSuppressedRegions([district, town]);
    expect(suppressed).toEqual(new Set([0]));
  });

  it('keeps both regions when neither contains the other', () => {
    const a: [number, number, number, number] = [0, 1, 0, 1];
    const b: [number, number, number, number] = [5, 6, 5, 6];
    expect(computeSuppressedRegions([a, b]).size).toBe(0);
  });

  it('keeps both when the boxes are identical (same place referenced twice)', () => {
    const a: [number, number, number, number] = [47.6, 48.2, 12.3, 12.9];
    const b: [number, number, number, number] = [47.6, 48.2, 12.3, 12.9];
    expect(computeSuppressedRegions([a, b]).size).toBe(0);
  });

  it('ignores null boxes', () => {
    const a: [number, number, number, number] = [0, 1, 0, 1];
    expect(computeSuppressedRegions([a, null]).size).toBe(0);
  });
});

describe('filterLocationsWithVisibleDots', () => {
  const town: LocationEntry = { mention: 'town', lat: 47.9, lon: 12.6, osm_id: '1' };
  const district: LocationEntry = { mention: 'district', lat: 48.0, lon: 12.7, osm_id: '2' };

  it('keeps only locations that have a matching visible dot for the report', () => {
    const dots = [makeDot({ report_id: 1, lat: 47.9, lon: 12.6 })];
    const result = filterLocationsWithVisibleDots([town, district], 1, dots);
    expect(result).toEqual([town]);
  });

  it('returns nothing when the report has no visible dots at all', () => {
    const dots = [makeDot({ report_id: 2, lat: 47.9, lon: 12.6 })];
    expect(filterLocationsWithVisibleDots([town], 1, dots)).toEqual([]);
  });

  it('does not match dots belonging to a different report', () => {
    const dots = [makeDot({ report_id: 1, lat: 47.9, lon: 12.6 }), makeDot({ report_id: 2, lat: 48.0, lon: 12.7 })];
    const result = filterLocationsWithVisibleDots([town, district], 1, dots);
    expect(result).toEqual([town]);
  });

  it('matches within the ~11m tolerance but not beyond it', () => {
    const dots = [makeDot({ report_id: 1, lat: 47.90005, lon: 12.60005 })];
    expect(filterLocationsWithVisibleDots([town], 1, dots)).toEqual([town]);

    const farDots = [makeDot({ report_id: 1, lat: 47.95, lon: 12.6 })];
    expect(filterLocationsWithVisibleDots([town], 1, farDots)).toEqual([]);
  });
});

describe('computeSuppressedDotsWithLocs', () => {
  it('suppresses the dot whose location contains another dot of the same report', () => {
    const districtDot = makeDot({ report_id: 1, lat: 48.0, lon: 12.5, location_bbox: [47.6, 48.2, 12.3, 12.9] });
    const townDot = makeDot({ report_id: 1, lat: 47.9, lon: 12.6, location_bbox: [47.83, 47.94, 12.58, 12.70] });
    const suppressed = computeSuppressedDotsWithLocs([districtDot, townDot], []);
    expect(suppressed).toEqual(new Set([districtDot]));
  });

  it('falls back to matching a LocationEntry by lat/lon when location_bbox is absent', () => {
    const districtLoc: LocationEntry = {
      osm_id: '1', lat: 48.0, lon: 12.5,
      polygon: { type: 'Polygon', coordinates: [[[12.3, 47.6], [12.9, 47.6], [12.9, 48.2], [12.3, 48.2], [12.3, 47.6]]] },
    };
    const townDot = makeDot({ report_id: 1, lat: 47.9, lon: 12.6, location_bbox: [47.83, 47.94, 12.58, 12.70] });
    const districtDot = makeDot({ report_id: 1, lat: 48.0, lon: 12.5 });
    const suppressed = computeSuppressedDotsWithLocs([districtDot, townDot], [districtLoc]);
    expect(suppressed).toEqual(new Set([districtDot]));
  });

  it('suppresses nothing for a single dot', () => {
    const dot = makeDot({ report_id: 1 });
    expect(computeSuppressedDotsWithLocs([dot], []).size).toBe(0);
  });
});

describe('computeVisibleReportBounds', () => {
  it('excludes suppressed dots from the computed bounds', () => {
    const districtDot = makeDot({ report_id: 1, lat: 48.0, lon: 12.5, location_bbox: [47.6, 48.2, 12.3, 12.9] });
    const townDot = makeDot({ report_id: 1, lat: 47.9, lon: 12.6, location_bbox: [47.83, 47.94, 12.58, 12.70] });
    const bounds = computeVisibleReportBounds([districtDot, townDot], []);
    // Bounds should match ONLY the town's bbox, not the (suppressed) district's.
    expect(bounds).toEqual([[47.83, 12.58], [47.94, 12.70]]);
  });

  it('returns null when there are no dots', () => {
    expect(computeVisibleReportBounds([], [])).toBeNull();
  });

  it('frames a single dot without a location_bbox using a small point box', () => {
    const dot = makeDot({ report_id: 1, lat: 10, lon: 20 });
    const bounds = computeVisibleReportBounds([dot], []);
    expect(bounds).toEqual([[9.99, 19.99], [10.01, 20.01]]);
  });
});

describe('osmKey / dedupByOsm', () => {
  it('normalizes short and long OSM type spellings to the same key', () => {
    expect(osmKey({ osm_id: '123', osm_type: 'R' })).toBe(osmKey({ osm_id: '123', osm_type: 'relation' }));
    expect(osmKey({ osm_id: '123', osm_type: 'N' })).toBe(osmKey({ osm_id: '123', osm_type: 'node' }));
    expect(osmKey({ osm_id: '123', osm_type: 'W' })).toBe(osmKey({ osm_id: '123', osm_type: 'way' }));
  });

  it('drops a duplicate entity referenced via both spellings (the real production case)', () => {
    const locs: LocationEntry[] = [
      { mention: 'Wald im LK Traunstein', osm_id: '2156363', osm_type: 'R' },
      { mention: 'LK Traunstein', osm_id: '2156363', osm_type: 'relation' },
    ];
    const result = dedupByOsm(locs);
    expect(result).toHaveLength(1);
    expect(result[0].mention).toBe('Wald im LK Traunstein');
  });

  it('is a no-op when every location is a distinct entity', () => {
    const locs: LocationEntry[] = [
      { osm_id: '1', osm_type: 'relation' },
      { osm_id: '2', osm_type: 'way' },
    ];
    expect(dedupByOsm(locs)).toHaveLength(2);
  });
});
