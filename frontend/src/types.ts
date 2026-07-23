export interface LocationEntry {
  mention?: string;
  name?: string;
  lat?: number;
  lon?: number;
  osm_id?: string;
  osm_type?: string;
  display_name?: string;
  boundingbox?: number[];
  polygon?: GeoJsonGeometry;
  /** Geocoding outcome for this mention: 'ok' | 'error' | 'no_candidates'. */
  status?: string | null;
  [key: string]: unknown;
}

export interface UserStateDTO {
  hide: boolean;
  flag: boolean;
  flag_author?: string | null;
  new: boolean;
  locations?: LocationEntry[] | null;
}

export interface ReportDTO {
  id: number;
  identifier: string;
  text: string;
  url: string;
  platform: string;
  timestamp: string; // ISO
  event_types: string[];
  relevance: 'high' | 'medium' | 'low' | 'none';
  /** 'ok' (default/legacy) | 'error' | 'no_text' — classification pipeline outcome for this post. */
  processing_status?: string | null;
  /** 'ok' (default/legacy) | 'error' — geo-recognition (mention extraction) pipeline outcome. */
  geo_recognition_status?: string | null;
  /** Zero or more of 'classification_failed' | 'no_text' | 'geo_recognition_failed' |
   * 'geoparsing_failed' — classification and the geo pipeline fail independently, so
   * a report can carry more than one at once. Empty when it isn't an issue. */
  issue_kinds?: string[];
  author?: string | null;
  locations: LocationEntry[];
  original_locations: LocationEntry[];
  user_state: UserStateDTO;
}

export interface ReportsResponse {
  reports: ReportDTO[];
  pending_count: number;
  loaded_at: string;
  /** Facet fields are null under the lean views (only_new/only_issues), where
   * the backend skips the facet scan: null = "not computed, keep what you had",
   * {} = a real empty result. */
  event_type_totals?: Record<string, number> | null;
  relevance_totals?: Record<string, number> | null;
  location_counts?: Record<string, number> | null;
  processing_status_totals?: Record<string, number>;
  reports_total_count?: number;
  reports_unseen_count?: number;
  all_platforms?: string[] | null;
  platform_counts?: Record<string, number> | null;
  platform_added_counts?: Record<string, number> | null;
  has_more?: boolean;
  total_count?: number;
  unseen_count?: number;
}

export interface LayerDTO {
  id: number;
  name: string;
}

export interface LayersResponse {
  layers: LayerDTO[];
}

export interface ScenarioDTO {
  id: number;
  name: string;
  description?: string;
}

export interface ScenariosResponse {
  scenarios: ScenarioDTO[];
}

export interface DotDTO {
  report_id: number;
  lat: number;
  lon: number;
  seen: boolean;
  hide: boolean;
  flag: boolean;
  new: boolean;
  location_name: string;
  location_display: string;
  text: string;
  author: string;
  platform: string;
  timestamp: string;
  event_types: string[];
  relevance: string;
  url: string;
  location_bbox_area?: number | null;
  location_bbox?: [number, number, number, number] | null;
}

export type GeoJsonGeometry = {
  type: string;
  coordinates: unknown[];
};

export type Lang = 'de' | 'en';

export interface FetchReportsParams {
  loc_filter?: string[];
  platforms?: string[];
  event_types?: string[];
  relevances?: string[];
  show_hidden?: boolean;
  show_flagged?: boolean;
  show_unflagged?: boolean;
  search?: string;
  limit?: number;
  time_window?: string;
  since?: string;
  until?: string;
  only_new?: boolean;
  only_issues?: boolean;
  /** Drawn-area filter: flat 'lat,lon,lat,lon,…' ring, applied server-side via PostGIS. */
  area?: string;
}

export interface ReportsBundleResponse extends ReportsResponse {
  dots: DotDTO[];
}

export interface NewCountParams {
  since: string;
  loc_filter?: string[];
  platforms?: string[];
  event_types?: string[];
  relevances?: string[];
  show_hidden?: boolean;
  show_flagged?: boolean;
  show_unflagged?: boolean;
  time_window?: string;
}

export interface NewCountResponse {
  count: number;
}

export interface DotsParams {
  loc_filter?: string[];
  platforms?: string[];
  event_types?: string[];
  relevances?: string[];
  show_hidden?: boolean;
  show_flagged?: boolean;
  show_unflagged?: boolean;
  search?: string;
  time_window?: string;
  since?: string;
  until?: string;
  only_new?: boolean;
  only_issues?: boolean;
  /** Drawn-area filter: flat 'lat,lon,lat,lon,…' ring, applied server-side via PostGIS. */
  area?: string;
}

export interface DemoStatus {
  demo_mode: boolean;
  running: boolean;
  done: number;
  total: number;
}

export interface NominatimResult {
  place_id: number;
  display_name: string;
  lat: string;
  lon: string;
  osm_id?: string;
  osm_type?: string;
  boundingbox?: string[];
  geojson?: GeoJsonGeometry;
}
