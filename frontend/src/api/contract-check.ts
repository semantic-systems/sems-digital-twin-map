/**
 * Pure type-level checks (zero runtime code/cost) that fail `tsc` when a
 * hand-written type in types.ts drifts from what the backend actually returns
 * or accepts, per the generated OpenAPI schema (schema.d.ts, regenerated via
 * `npm run gen:types` from backend/openapi.json — itself regenerated via
 * `python backend/scripts/export_openapi.py`).
 *
 * This exists because a hand-maintained frontend type and the backend route
 * it describes can silently drift — exactly what happened earlier: `only_new`
 * was added to three backend query parameters but initially missing from one
 * hand-written frontend params type, and nothing caught it until the bug was
 * observed at runtime. These checks turn that class of mistake into a build
 * error instead.
 *
 * Response DTOs keep their own hand-written types in types.ts (not aliases
 * into `components['schemas'][...]` directly) because several fields are
 * deliberately narrower than what the backend's Pydantic models declare —
 * e.g. `ReportDTO.relevance` as a string union, `DotDTO.location_bbox` as a
 * 4-tuple, `LocationEntry.polygon` as GeoJsonGeometry instead of a bare
 * `Record<string, unknown>`. Those are intentional refinements, not
 * accidental duplication, so this file checks that the KEY SETS match
 * (nothing added/removed/renamed) rather than forcing full type identity.
 */
import type { components, operations } from './schema';
import type {
  ReportDTO,
  DotDTO,
  UserStateDTO,
  LocationEntry,
  ReportsResponse,
  ReportsBundleResponse,
  LayerDTO,
  LayersResponse,
  ScenarioDTO,
  ScenariosResponse,
  NewCountResponse,
  FetchReportsParams,
  DotsParams,
} from '../types';

// If the two sides' key sets differ, this resolves to an object type naming
// exactly which keys are missing from which side (instead of `true`) — read
// the resulting compile error to see what drifted.
type KeysEqual<HandWritten, Generated> =
  keyof HandWritten extends keyof Generated
    ? keyof Generated extends keyof HandWritten
      ? true
      : { MISSING_FROM_HAND_WRITTEN_TYPE: Exclude<keyof Generated, keyof HandWritten> }
    : { MISSING_FROM_GENERATED_SCHEMA_OR_RENAMED: Exclude<keyof HandWritten, keyof Generated> };

type Assert<T extends true> = T;

// --- Response DTOs: full key-set parity with the backend Pydantic models ---
export type _ReportDTO = Assert<KeysEqual<ReportDTO, components['schemas']['ReportDTO']>>;
export type _DotDTO = Assert<KeysEqual<DotDTO, components['schemas']['DotDTO']>>;
export type _UserStateDTO = Assert<KeysEqual<UserStateDTO, components['schemas']['UserStateDTO']>>;
export type _LocationEntry = Assert<KeysEqual<LocationEntry, components['schemas']['LocationEntry']>>;
export type _ReportsResponse = Assert<KeysEqual<ReportsResponse, components['schemas']['ReportsResponse']>>;
export type _ReportsBundleResponse = Assert<KeysEqual<ReportsBundleResponse, components['schemas']['ReportsBundleResponse']>>;
export type _LayerDTO = Assert<KeysEqual<LayerDTO, components['schemas']['LayerDTO']>>;
export type _LayersResponse = Assert<KeysEqual<LayersResponse, components['schemas']['LayersResponse']>>;
export type _ScenarioDTO = Assert<KeysEqual<ScenarioDTO, components['schemas']['ScenarioDTO']>>;
export type _ScenariosResponse = Assert<KeysEqual<ScenariosResponse, components['schemas']['ScenariosResponse']>>;
export type _NewCountResponse = Assert<KeysEqual<NewCountResponse, components['schemas']['NewCountResponse']>>;

// --- Request query params: only the fields shared VERBATIM by name ---
// (platforms/event_types/relevances are intentionally renamed server-side via
// FastAPI's alias= to platform/event_type/relevance for a plural-vs-singular
// query string convention, so they can never structurally match by name — that
// remapping lives in toBackendParams()/dotsParamsFromFilters(), not here.)
// Pick<T, K> itself fails to compile if any listed key is missing from T, so
// simply picking the same literal key list from both sides is the check.
type FetchReportsSharedKeys =
  | 'username' | 'show_hidden' | 'show_flagged' | 'show_unflagged'
  | 'search' | 'time_window' | 'since' | 'until' | 'only_new' | 'area' | 'limit';
export type _FetchReportsParams_Frontend = Pick<FetchReportsParams, FetchReportsSharedKeys>;
export type _FetchReportsParams_Backend = Pick<
  operations['get_reports_endpoint_api_v1_reports__get']['parameters']['query'],
  FetchReportsSharedKeys
>;

type DotsSharedKeys =
  | 'username' | 'show_hidden' | 'show_flagged' | 'show_unflagged'
  | 'search' | 'time_window' | 'since' | 'until' | 'only_new' | 'area';
export type _DotsParams_Frontend = Pick<DotsParams, DotsSharedKeys>;
export type _DotsParams_Backend = Pick<
  operations['dots_endpoint_api_v1_reports_dots_get']['parameters']['query'],
  DotsSharedKeys
>;
export type _BundleParams_Backend = Pick<
  operations['bundle_endpoint_api_v1_reports_bundle_get']['parameters']['query'],
  FetchReportsSharedKeys
>;
