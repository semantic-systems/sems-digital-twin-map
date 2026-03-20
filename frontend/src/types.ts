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
  event_type: string;
  relevance: 'high' | 'medium' | 'low' | 'none';
  author?: string | null;
  locations: LocationEntry[];
  original_locations: LocationEntry[];
  user_state: UserStateDTO;
}

export interface ReportsResponse {
  reports: ReportDTO[];
  pending_count: number;
  loaded_at: string;
  event_type_totals?: Record<string, number>;
  all_platforms?: string[];
  platform_counts?: Record<string, number>;
  platform_added_counts?: Record<string, number>;
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
  new: boolean;
  location_name: string;
  location_display: string;
  text: string;
  author: string;
  platform: string;
  timestamp: string;
  event_type: string;
  relevance: string;
  url: string;
}

export type GeoJsonGeometry = {
  type: string;
  coordinates: unknown[];
};

export type Lang = 'de' | 'en';

export interface FetchReportsParams {
  username: string;
  loc_filter?: string;
  platforms?: string[];
  event_types?: string[];
  relevances?: string[];
  show_hidden?: boolean;
  show_flagged?: boolean;
  show_unflagged?: boolean;
}

export interface NewCountParams {
  username: string;
  since: string;
  loc_filter?: string;
  platforms?: string[];
  event_types?: string[];
  relevances?: string[];
  show_hidden?: boolean;
  show_flagged?: boolean;
  show_unflagged?: boolean;
}

export interface NewCountResponse {
  count: number;
}

export interface DotsParams {
  username: string;
  loc_filter?: string;
  platforms?: string[];
  event_types?: string[];
  relevances?: string[];
  show_hidden?: boolean;
  show_flagged?: boolean;
  show_unflagged?: boolean;
}

export interface UserStateResponse {
  username: string;
  state: Record<number, UserStateDTO>;
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
