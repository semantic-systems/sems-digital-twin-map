import { apiFetch, buildQuery } from './client';
import type {
  ReportsResponse,
  ReportsBundleResponse,
  ReportDTO,
  FetchReportsParams,
  NewCountParams,
  NewCountResponse,
  DotsParams,
  DotDTO,
  LocationEntry,
} from '../types';

// The backend uses singular aliases: ?platform=, ?event_type=, ?relevance=
// The frontend stores use plural names, so we remap here.
function toBackendParams(p: FetchReportsParams | NewCountParams | DotsParams): Record<string, unknown> {
  return {
    username: p.username,
    loc_filter: (p as FetchReportsParams).loc_filter,
    platform: p.platforms,
    event_type: p.event_types,
    relevance: p.relevances,
    show_hidden: p.show_hidden,
    show_flagged: p.show_flagged,
    show_unflagged: p.show_unflagged,
    time_window: p.time_window !== 'all' ? p.time_window : undefined,
    ...(('since' in p && (p as { since?: string }).since) ? { since: (p as { since: string }).since } : {}),
    ...(('until' in p && (p as { until?: string }).until) ? { until: (p as { until: string }).until } : {}),
    ...((p as DotsParams).search ? { search: (p as DotsParams).search } : {}),
    ...((p as DotsParams).only_new ? { only_new: true } : {}),
  };
}

const BASE_LIMIT = 200;

export async function fetchReports(params: FetchReportsParams): Promise<ReportsResponse> {
  const qs = buildQuery({
    ...toBackendParams(params),
    limit: params.limit ?? BASE_LIMIT,
  });
  return apiFetch<ReportsResponse>(`/reports/${qs}`);
}

// Reports list + map dots in one request. Preferred over calling fetchReports and
// fetchDots separately on a filter change: one round trip instead of two competing
// for the single sync worker.
export async function fetchReportsBundle(params: FetchReportsParams): Promise<ReportsBundleResponse> {
  const qs = buildQuery({
    ...toBackendParams(params),
    limit: params.limit ?? BASE_LIMIT,
  });
  return apiFetch<ReportsBundleResponse>(`/reports/bundle${qs}`);
}

export async function fetchNewCount(params: NewCountParams): Promise<NewCountResponse> {
  const qs = buildQuery(toBackendParams(params));
  return apiFetch<NewCountResponse>(`/reports/new-count${qs}`);
}

export async function fetchDots(params: DotsParams): Promise<{ dots: DotDTO[] }> {
  const qs = buildQuery(toBackendParams(params));
  return apiFetch<{ dots: DotDTO[] }>(`/reports/dots${qs}`);
}

export async function fetchReport(id: number, username?: string): Promise<ReportDTO> {
  const qs = username ? `?username=${encodeURIComponent(username)}` : '';
  return apiFetch<ReportDTO>(`/reports/${id}${qs}`);
}

/** The onboarding tour's permanent example report (see tour/exampleReport.ts). */
export async function fetchTourExample(username: string): Promise<ReportDTO> {
  return apiFetch<ReportDTO>(`/reports/tour-example?username=${encodeURIComponent(username)}`);
}

export async function fetchPlatforms(username: string): Promise<{ platforms: string[] }> {
  return apiFetch<{ platforms: string[] }>(`/reports/platforms?username=${encodeURIComponent(username)}`);
}

export async function admitReports(username: string, report_ids: number[]): Promise<void> {
  await apiFetch<void>('/reports/admit', {
    method: 'POST',
    body: JSON.stringify({ username, report_ids }),
  });
}

export async function admitAllReports(
  username: string,
  filters?: { platforms?: string[]; event_types?: string[]; relevances?: string[] },
): Promise<{ admitted: number }> {
  return apiFetch<{ admitted: number }>('/reports/admit-all', {
    method: 'POST',
    body: JSON.stringify({ username, ...filters }),
  });
}

export async function hideReport(id: number, username: string, hide: boolean): Promise<void> {
  await apiFetch<void>(`/reports/${id}/hide`, {
    method: 'PATCH',
    body: JSON.stringify({ username, hide }),
  });
}

export async function flagReport(id: number, username: string, flag: boolean): Promise<void> {
  await apiFetch<void>(`/reports/${id}/flag`, {
    method: 'PATCH',
    body: JSON.stringify({ username, flag }),
  });
}

export async function acknowledgeReport(id: number, username: string): Promise<void> {
  await apiFetch<void>(`/reports/${id}/acknowledge`, {
    method: 'PATCH',
    body: JSON.stringify({ username }),
  });
}

export async function updateLocations(
  id: number,
  username: string,
  locations: LocationEntry[],
): Promise<void> {
  await apiFetch<void>(`/reports/${id}/locations`, {
    method: 'PATCH',
    body: JSON.stringify({ username, locations }),
  });
}

export async function restoreLocations(id: number, username: string): Promise<void> {
  await apiFetch<void>(`/reports/${id}/locations`, {
    method: 'DELETE',
    body: JSON.stringify({ username }),
  });
}
