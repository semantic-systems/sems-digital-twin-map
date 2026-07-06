import { describe, it, expect, beforeEach } from 'vitest';
import { useReportStore } from './useReportStore';
import type { ReportDTO } from '../types';

function makeReport(overrides: Partial<ReportDTO> = {}): ReportDTO {
  return {
    id: 1,
    identifier: 'r1',
    text: 'text',
    url: '',
    platform: 'mastodon',
    timestamp: '2026-01-01T00:00:00Z',
    event_types: [],
    relevance: 'high',
    author: 'alice',
    locations: [],
    original_locations: [],
    user_state: { hide: false, flag: false, flag_author: null, new: true, locations: null },
    ...overrides,
  };
}

// Zustand stores are plain modules holding global state — reset it before each
// test so tests don't leak state into one another.
function resetStore() {
  useReportStore.setState({
    reports: [], dots: [], pinnedReport: null, activeReportId: null,
    pendingNewCount: 0, loadedAt: null, eventTypeTotals: {}, relevanceTotals: {},
    locationCounts: {}, reloadTrigger: 0, hasMore: false, totalCount: 0,
    currentLimit: 200, unseenCount: 0, isLoading: false,
  });
}

beforeEach(resetStore);

describe('setReports facet-count preservation', () => {
  it('overwrites facet counts when they are explicitly provided', () => {
    useReportStore.getState().setReports([], 't', { high: 1 }, { medium: 2 }, false, { localized: 3 }, 10, 5);
    const s = useReportStore.getState();
    expect(s.eventTypeTotals).toEqual({ high: 1 });
    expect(s.relevanceTotals).toEqual({ medium: 2 });
    expect(s.locationCounts).toEqual({ localized: 3 });
    expect(s.totalCount).toBe(10);
    expect(s.unseenCount).toBe(5);
  });

  it('PRESERVES the previous facet counts when omitted (the "only new" lean-load path)', () => {
    useReportStore.getState().setReports([], 't', { high: 1 }, { medium: 2 }, false, { localized: 3 }, 10, 5);
    // Simulate a subsequent "only new" load: backend returns empty facet dicts,
    // so the caller passes undefined instead of {} to signal "don't touch these".
    useReportStore.getState().setReports([], 't2', undefined, undefined, false, undefined, 2, 2);
    const s = useReportStore.getState();
    expect(s.eventTypeTotals).toEqual({ high: 1 });
    expect(s.relevanceTotals).toEqual({ medium: 2 });
    expect(s.locationCounts).toEqual({ localized: 3 });
    // totalCount and unseenCount are NOT preserved — they always reflect the
    // latest load (only_new legitimately narrows total_count/unseen_count).
    expect(s.totalCount).toBe(2);
    expect(s.unseenCount).toBe(2);
  });

  it('clears facet counts when explicitly passed an empty object', () => {
    useReportStore.getState().setReports([], 't', { high: 1 }, {}, false, {}, 0, 0);
    useReportStore.getState().setReports([], 't2', {}, {}, false, {}, 0, 0);
    expect(useReportStore.getState().eventTypeTotals).toEqual({});
  });
});

describe('optimisticAcknowledge', () => {
  it('decrements unseenCount when the report was contributing to the badge', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, user_state: { hide: false, flag: false, flag_author: null, new: true, locations: null } })],
      unseenCount: 3,
    });
    useReportStore.getState().optimisticAcknowledge(1);
    expect(useReportStore.getState().unseenCount).toBe(2);
    expect(useReportStore.getState().reports[0].user_state.new).toBe(false);
  });

  it('does not decrement when the report was already not-new', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, user_state: { hide: false, flag: false, flag_author: null, new: false, locations: null } })],
      unseenCount: 3,
    });
    useReportStore.getState().optimisticAcknowledge(1);
    expect(useReportStore.getState().unseenCount).toBe(3);
  });

  it('never drops unseenCount below zero', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, user_state: { hide: false, flag: false, flag_author: null, new: true, locations: null } })],
      unseenCount: 0,
    });
    useReportStore.getState().optimisticAcknowledge(1);
    expect(useReportStore.getState().unseenCount).toBe(0);
  });

  it('acknowledges a pinned report not present in the loaded reports list', () => {
    useReportStore.setState({
      reports: [],
      pinnedReport: makeReport({ id: 99, user_state: { hide: false, flag: false, flag_author: null, new: true, locations: null } }),
      unseenCount: 1,
    });
    useReportStore.getState().optimisticAcknowledge(99);
    expect(useReportStore.getState().unseenCount).toBe(0);
    expect(useReportStore.getState().pinnedReport?.user_state.new).toBe(false);
  });

  it('also clears the new flag on the matching dot', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, user_state: { hide: false, flag: false, flag_author: null, new: true, locations: null } })],
      dots: [{ report_id: 1, lat: 0, lon: 0, seen: false, hide: false, flag: false, new: true,
                location_name: '', location_display: '', text: '', author: '', platform: 'mastodon',
                timestamp: '', event_types: [], relevance: 'high', url: '' }],
    });
    useReportStore.getState().optimisticAcknowledge(1);
    expect(useReportStore.getState().dots[0].new).toBe(false);
  });
});

describe('optimisticHide', () => {
  it('decrements unseenCount when hiding a new report that was contributing', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, relevance: 'high', user_state: { hide: false, flag: false, flag_author: null, new: true, locations: null } })],
      unseenCount: 2,
    });
    useReportStore.getState().optimisticHide(1, true);
    expect(useReportStore.getState().unseenCount).toBe(1);
    expect(useReportStore.getState().reports[0].user_state.hide).toBe(true);
  });

  it('restores unseenCount when un-hiding a new report', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, user_state: { hide: true, flag: false, flag_author: null, new: true, locations: null } })],
      unseenCount: 1,
    });
    useReportStore.getState().optimisticHide(1, false);
    expect(useReportStore.getState().unseenCount).toBe(2);
  });

  it('does not touch unseenCount for a report that is not new', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, user_state: { hide: false, flag: false, flag_author: null, new: false, locations: null } })],
      unseenCount: 5,
    });
    useReportStore.getState().optimisticHide(1, true);
    expect(useReportStore.getState().unseenCount).toBe(5);
  });

  it("counts ALL relevances (badge is no longer high/medium-only)", () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, relevance: 'low', user_state: { hide: false, flag: false, flag_author: null, new: true, locations: null } })],
      unseenCount: 1,
    });
    useReportStore.getState().optimisticHide(1, true);
    expect(useReportStore.getState().unseenCount).toBe(0);
  });
});

describe('optimisticFlag', () => {
  it('flags every report by the same author', () => {
    useReportStore.setState({
      reports: [
        makeReport({ id: 1, author: 'alice' }),
        makeReport({ id: 2, author: 'alice' }),
        makeReport({ id: 3, author: 'bob' }),
      ],
    });
    useReportStore.getState().optimisticFlag('alice', true);
    const s = useReportStore.getState();
    expect(s.reports[0].user_state.flag).toBe(true);
    expect(s.reports[1].user_state.flag).toBe(true);
    expect(s.reports[2].user_state.flag).toBe(false);
    expect(s.reports[0].user_state.flag_author).toBe('alice');
  });

  it('clears flag_author when unflagging', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, author: 'alice', user_state: { hide: false, flag: true, flag_author: 'alice', new: false, locations: null } })],
    });
    useReportStore.getState().optimisticFlag('alice', false);
    expect(useReportStore.getState().reports[0].user_state.flag_author).toBeNull();
  });
});

describe('optimisticUpdateLocations / optimisticRestoreLocations', () => {
  it('updates only the targeted report', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1 }), makeReport({ id: 2 })],
    });
    const newLocs = [{ mention: 'x', lat: 1, lon: 2 }];
    useReportStore.getState().optimisticUpdateLocations(1, newLocs);
    const s = useReportStore.getState();
    expect(s.reports[0].locations).toEqual(newLocs);
    expect(s.reports[0].user_state.locations).toEqual(newLocs);
    expect(s.reports[1].locations).toEqual([]);
  });

  it('restore sets user_state.locations back to null (falls back to original_locations)', () => {
    useReportStore.setState({
      reports: [makeReport({ id: 1, user_state: { hide: false, flag: false, flag_author: null, new: false, locations: [{ mention: 'edited' }] } })],
    });
    const original = [{ mention: 'original' }];
    useReportStore.getState().optimisticRestoreLocations(1, original);
    const s = useReportStore.getState();
    expect(s.reports[0].locations).toEqual(original);
    expect(s.reports[0].user_state.locations).toBeNull();
  });
});
