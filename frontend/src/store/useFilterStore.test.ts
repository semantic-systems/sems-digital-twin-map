import { describe, it, expect } from 'vitest';
import { activeLocFilter, dotsParamsFromFilters, getLayerColor } from './useFilterStore';

describe('activeLocFilter', () => {
  it('returns undefined when all three location types are shown (no restriction)', () => {
    expect(activeLocFilter({
      locShowLocalized: true, locShowPending: true, locShowUnlocalized: true,
    })).toBeUndefined();
  });

  it('returns only the active subset when some are toggled off', () => {
    expect(activeLocFilter({
      locShowLocalized: true, locShowPending: false, locShowUnlocalized: true,
    })).toEqual(['localized', 'unlocalized']);
  });

  it('returns an empty array when all three are toggled off', () => {
    expect(activeLocFilter({
      locShowLocalized: false, locShowPending: false, locShowUnlocalized: false,
    })).toEqual([]);
  });
});

function baseFilters(overrides: Partial<Parameters<typeof dotsParamsFromFilters>[1]> = {}) {
  return {
    platforms: [],
    allPlatforms: ['bluesky', 'mastodon'],
    eventTypes: ['Sonstiges'],
    relevances: ['high'],
    showHidden: false,
    showFlagged: true,
    showUnflagged: true,
    search: '',
    timeWindow: 'all',
    customSince: null,
    customUntil: null,
    showOnlyNew: false,
    locShowLocalized: true,
    locShowPending: true,
    locShowUnlocalized: true,
    ...overrides,
  };
}

describe('dotsParamsFromFilters', () => {
  it('falls back to allPlatforms when no platform is explicitly selected', () => {
    const params = dotsParamsFromFilters('alice', baseFilters());
    expect(params.platforms).toEqual(['bluesky', 'mastodon']);
  });

  it('uses the explicit platform selection when present', () => {
    const params = dotsParamsFromFilters('alice', baseFilters({ platforms: ['bluesky'] }));
    expect(params.platforms).toEqual(['bluesky']);
  });

  it('omits search when empty, includes it when set', () => {
    expect(dotsParamsFromFilters('alice', baseFilters()).search).toBeUndefined();
    expect(dotsParamsFromFilters('alice', baseFilters({ search: 'fire' })).search).toBe('fire');
  });

  it('only includes since/until when timeWindow is "custom"', () => {
    const preset = dotsParamsFromFilters('alice', baseFilters({
      timeWindow: '1d', customSince: '2026-01-01', customUntil: '2026-01-02',
    }));
    expect(preset.since).toBeUndefined();
    expect(preset.until).toBeUndefined();

    const custom = dotsParamsFromFilters('alice', baseFilters({
      timeWindow: 'custom', customSince: '2026-01-01', customUntil: '2026-01-02',
    }));
    expect(custom.since).toBe('2026-01-01');
    expect(custom.until).toBe('2026-01-02');
  });

  it('omits only_new when false, sets it true when showOnlyNew is on', () => {
    expect(dotsParamsFromFilters('alice', baseFilters()).only_new).toBeUndefined();
    expect(dotsParamsFromFilters('alice', baseFilters({ showOnlyNew: true })).only_new).toBe(true);
  });

  it('derives loc_filter via activeLocFilter (undefined when all three shown)', () => {
    expect(dotsParamsFromFilters('alice', baseFilters()).loc_filter).toBeUndefined();
    expect(
      dotsParamsFromFilters('alice', baseFilters({ locShowPending: false })).loc_filter,
    ).toEqual(['localized', 'unlocalized']);
  });

  it('passes through username, event types, relevances and show-flags verbatim', () => {
    const params = dotsParamsFromFilters('alice', baseFilters({
      eventTypes: ['Sonstiges', 'Bedarfe & Anfragen'],
      relevances: ['high', 'medium'],
      showHidden: true, showFlagged: false, showUnflagged: true,
    }));
    expect(params.username).toBe('alice');
    expect(params.event_types).toEqual(['Sonstiges', 'Bedarfe & Anfragen']);
    expect(params.relevances).toEqual(['high', 'medium']);
    expect(params.show_hidden).toBe(true);
    expect(params.show_flagged).toBe(false);
    expect(params.show_unflagged).toBe(true);
  });
});

describe('getLayerColor', () => {
  const layers = [{ id: 10, name: 'a' }, { id: 20, name: 'b' }, { id: 30, name: 'c' }];

  it('derives a stable color from a layer\'s position in the list', () => {
    const first = getLayerColor(10, layers);
    const second = getLayerColor(20, layers);
    expect(first).not.toBe(second);
    // Stable: same id, same list -> same color every time.
    expect(getLayerColor(10, layers)).toBe(first);
  });

  it('falls back to a default color for an id not present in the list', () => {
    expect(getLayerColor(999, layers)).toBe('#6366f1');
  });
});
