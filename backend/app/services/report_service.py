from __future__ import annotations

"""
report_service.py
-----------------
All business logic for the /api/v1/reports endpoints.
Ports the equivalent Dash-callback logic from src/app/layout/map/map.py
and src/app/layout/map/sidebar.py into plain functions that accept a
SQLAlchemy Session and return plain Python / Pydantic objects.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import String, cast, case, and_, or_, func
from sqlalchemy import Text as SaText
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..db import LocationPolygon, Report, UserAdmission, UserReportState
from ..schemas.report import LocationEntry, ReportDTO, UserStateDTO

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _polygon_bbox(polygon: dict) -> list[float] | None:
    """Return [min_lat, max_lat, min_lon, max_lon] for an area/line GeoJSON geometry.

    Handles lines as well as polygons so a more-specific street dot can suppress a
    containing area dot. Point geometries are intentionally NOT handled: stored
    point coordinates have an unreliable lat/lon order, and a node's authoritative
    position is the dot's own lat/lon (used directly for suppression and centering),
    so deriving a bbox here would risk a swapped, far-off box.
    """
    ptype = polygon.get("type")
    raw = polygon.get("coordinates")
    if not raw:
        return None
    if ptype == "Polygon":
        flat = [pt for ring in raw for pt in ring]
    elif ptype == "MultiPolygon":
        flat = [pt for poly in raw for ring in poly for pt in ring]
    elif ptype == "LineString":
        flat = raw
    elif ptype == "MultiLineString":
        flat = [pt for line in raw for pt in line]
    else:
        return None
    if not flat:
        return None
    lons = [c[0] for c in flat]
    lats = [c[1] for c in flat]
    return [min(lats), max(lats), min(lons), max(lons)]


# Photon uses single-letter osm_type codes; Nominatim uses full words.
# Both forms may coexist in location_polygons depending on which geocoder
# produced the linked entity.
_SHORT_TO_LONG: dict[str, str] = {'R': 'relation', 'N': 'node', 'W': 'way'}
_LONG_TO_SHORT: dict[str, str] = {v: k for k, v in _SHORT_TO_LONG.items()}


def _alt_osm_type(osm_type: str) -> str | None:
    """Return the alternative spelling for an osm_type, or None if already canonical."""
    return _SHORT_TO_LONG.get(osm_type) or _LONG_TO_SHORT.get(osm_type)


def _osm_keys_with_alts(keys: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """Expand a set of (osm_id, osm_type) pairs to also include alternative spellings."""
    expanded = set(keys)
    for oid, otype in keys:
        alt = _alt_osm_type(otype)
        if alt:
            expanded.add((oid, alt))
    return list(expanded)


# Max (osm_id, osm_type) pairs per polygon lookup. A single tuple-IN over every
# location in the DB (e.g. an unfiltered "all" search → thousands of keys) produces
# a statement Postgres rejects, so we query in chunks and merge. 500 pairs = 1000
# bind params per statement, comfortably within limits.
_POLYGON_LOOKUP_CHUNK = 500


def _query_location_polygons(session: Session, keys: set[tuple[str, str]]) -> list:
    """Fetch LocationPolygon rows for the given (osm_id, osm_type) keys (plus their
    alternative osm_type spellings), batched to keep each IN clause small enough."""
    from sqlalchemy import tuple_

    expanded = _osm_keys_with_alts(keys)
    rows: list = []
    for i in range(0, len(expanded), _POLYGON_LOOKUP_CHUNK):
        chunk = expanded[i : i + _POLYGON_LOOKUP_CHUNK]
        rows.extend(
            session.query(LocationPolygon)
            .filter(tuple_(LocationPolygon.osm_id, LocationPolygon.osm_type).in_(chunk))
            .all()
        )
    return rows


def _best_polygon(poly_map: dict[tuple[str, str], Any], osm_id: str, osm_type: str) -> Any:
    """
    Look up a polygon preferring the canonical (long) form of osm_type.
    Falls back to the short form if the canonical entry is absent.
    """
    canonical = _SHORT_TO_LONG.get(osm_type, osm_type)
    short = _LONG_TO_SHORT.get(osm_type, osm_type)
    return (
        poly_map.get((osm_id, canonical))
        or poly_map.get((osm_id, short))
        or poly_map.get((osm_id, osm_type))
    )


def _coerce_locations(raw: Any) -> list[LocationEntry]:
    """Safely coerce a raw JSON list (from DB) to list[LocationEntry]."""
    if not raw:
        return []
    if isinstance(raw, list):
        result: list[LocationEntry] = []
        for item in raw:
            if isinstance(item, dict):
                # osm_id may be stored as int in older data — coerce to str
                if "osm_id" in item and item["osm_id"] is not None:
                    item = {**item, "osm_id": str(item["osm_id"])}
                result.append(LocationEntry(**item))
            elif isinstance(item, LocationEntry):
                result.append(item)
        return result
    return []


# ---------------------------------------------------------------------------
# enrich_with_polygons
# ---------------------------------------------------------------------------

def enrich_with_polygons(session: Session, locations: list) -> list:
    """
    Re-attach polygon data from location_polygons for a single report's locations.
    Used by the single-report detail endpoint so ActiveReportPolygons can render shapes.
    Queries with both short (R/N/W) and long (relation/node/way) osm_type spellings and
    prefers the canonical long form when both are present.
    """
    base_keys: set[tuple[str, str]] = {
        (str(loc["osm_id"]), str(loc["osm_type"]))
        for loc in locations
        if isinstance(loc, dict) and loc.get("osm_id") and loc.get("osm_type")
    }
    if not base_keys:
        return locations

    rows = _query_location_polygons(session, base_keys)
    poly_map = {(r.osm_id, r.osm_type): r.polygon for r in rows}

    return [
        {**loc, "polygon": poly}
        if isinstance(loc, dict)
           and (poly := _best_polygon(poly_map, str(loc.get("osm_id", "")), str(loc.get("osm_type", ""))))
        else loc
        for loc in locations
    ]


# ---------------------------------------------------------------------------
# get_user_state
# ---------------------------------------------------------------------------

@dataclass
class UserState:
    """A user's complete per-report state, loaded once per request.

    Admission is the watermark (see UserAdmission): a report is admitted iff
    report.id <= admitted_up_to. "New" is derived, not stored per admitted
    report: a report is new iff it is admitted and NOT in acknowledged_ids
    (rows are only written on acknowledge, so the stored set stays bounded by
    what the user actually clicked — not by everything ever admitted).
    """
    hidden_ids: set[int] = field(default_factory=set)
    flagged_authors: set[str] = field(default_factory=set)
    locs_map: dict[int, list] = field(default_factory=dict)
    admitted_up_to: int = 0
    acknowledged_ids: set[int] = field(default_factory=set)

    def is_new(self, report_id: int) -> bool:
        return report_id <= self.admitted_up_to and report_id not in self.acknowledged_ids


def get_user_state(
    username: str,
    session: Session,
) -> UserState:
    rows: list[UserReportState] = (
        session.query(UserReportState)
        .filter(UserReportState.username == username)
        .all()
    )

    state = UserState()
    for row in rows:
        rid = row.report_id
        if row.hide:
            state.hidden_ids.add(rid)
        if row.flag and row.flag_author:
            state.flagged_authors.add(row.flag_author)
        if row.locations is not None:
            state.locs_map[rid] = row.locations
        if not row.new:
            state.acknowledged_ids.add(rid)

    admission: UserAdmission | None = session.get(UserAdmission, username)
    if admission is not None:
        state.admitted_up_to = admission.admitted_up_to_id

    return state


# ---------------------------------------------------------------------------
# upsert_user_state
# ---------------------------------------------------------------------------

def upsert_user_state(
    username: str,
    report_id: int,
    session: Session,
    **kwargs: Any,
) -> None:
    """
    PostgreSQL INSERT … ON CONFLICT DO UPDATE for UserReportState.
    Silently skips if report_id does not exist in reports.
    """
    # Guard: ensure the report actually exists
    exists = session.query(Report.id).filter(Report.id == report_id).scalar()
    if exists is None:
        return

    insert_values: dict[str, Any] = {
        "username": username,
        "report_id": report_id,
        **kwargs,
    }

    stmt = pg_insert(UserReportState).values(**insert_values)

    update_values = {k: stmt.excluded[k] for k in kwargs}
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_report",
        set_=update_values,
    )

    session.execute(stmt)
    session.commit()


# ---------------------------------------------------------------------------
# advance_admission
# ---------------------------------------------------------------------------

def advance_admission(
    username: str,
    session: Session,
    up_to_id: int | None = None,
) -> int:
    """
    Advance the user's admission watermark to `up_to_id` (default: the current
    max report id, i.e. "admit everything ingested so far"). The watermark only
    ever moves forward (GREATEST), so concurrent admits can't regress it.
    Returns how many reports the move newly admitted.

    Note the semantic simplification vs the old per-report first_seen_at rows:
    admission is a plain prefix of ingestion order — the active view filters
    control what you SEE, not what gets admitted. Nothing still appears in the
    sidebar without an explicit admit (banner click or auto-update), which is
    the property the admission concept exists for.
    """
    if up_to_id is None:
        up_to_id = session.query(func.max(Report.id)).scalar() or 0

    previous = session.get(UserAdmission, username)
    old_watermark = previous.admitted_up_to_id if previous is not None else 0

    stmt = pg_insert(UserAdmission).values(
        username=username, admitted_up_to_id=up_to_id
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserAdmission.__table__.c.username],
        set_={
            "admitted_up_to_id": func.greatest(
                UserAdmission.__table__.c.admitted_up_to_id,
                stmt.excluded.admitted_up_to_id,
            ),
        },
    )
    session.execute(stmt)
    session.commit()

    if up_to_id <= old_watermark:
        return 0
    return (
        session.query(func.count(Report.id))
        .filter(Report.id > old_watermark, Report.id <= up_to_id)
        .scalar()
        or 0
    )


# ---------------------------------------------------------------------------
# normalize_filters
# ---------------------------------------------------------------------------

ALL_PLATFORMS = [
    "mastodon",
    "bluesky",
    "reddit",
    "rss",
    "twitter",
    "facebook",
    "instagram",
    "youtube",
    "telegram",
    "web",
]

ALL_EVENT_TYPES = [
    "Irrelevant",
    "Menschen betroffen",
    "Warnungen & Hinweise",
    "Evakuierungen & Umsiedlungen",
    "Spenden & Freiwillige",
    "Infrastruktur-Schäden",
    "Verletzte & Tote",
    "Vermisste & Gefundene",
    "Bedarfe & Anfragen",
    "Einsatzmaßnahmen",
    "Mitgefühl & Unterstützung",
    "Sonstiges",
]

ALL_RELEVANCE_TYPES = ["high", "medium", "low", "none"]


def normalize_filters(
    filter_platform: list[str] | None,
    filter_event_type: list[str] | None,
    filter_relevance_type: list[str] | None,
) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
    """
    Returns (eff_platform, eff_events, eff_relevance).
    None means "no filter / all selected".
    Empty list means "filter blocks everything".
    """
    eff_platform: list[str] | None = filter_platform if filter_platform else None

    if not filter_event_type or set(filter_event_type) >= set(ALL_EVENT_TYPES):
        eff_events: list[str] | None = None
    else:
        eff_events = filter_event_type

    if not filter_relevance_type or set(filter_relevance_type) >= set(ALL_RELEVANCE_TYPES):
        eff_relevance: list[str] | None = None
    else:
        eff_relevance = filter_relevance_type

    return eff_platform, eff_events, eff_relevance


# ---------------------------------------------------------------------------
# build_report_query
# ---------------------------------------------------------------------------

_ISSUE_STATUSES = ('error', 'no_text')


def build_report_query(
    session: Session,
    since: datetime | None = None,
    until: datetime | None = None,
    admitted_up_to: int | None = None,
    eff_platform: list[str] | None = None,
    eff_events: list[str] | None = None,
    eff_relevance: list[str] | None = None,
    demo_mode: bool = False,
    search: str | None = None,
    loc_filter: list[str] | None = None,
    only_issues: bool = False,
):
    """
    Returns a SQLAlchemy Query[Report] with all filters applied.
    Does NOT call .all() — callers may add further ordering / limits.
    loc_filter: None or all three values means no restriction; a strict subset
    filters to reports matching any of the listed location types.
    only_issues: restricts to reports worth operator attention. Classification and
    the geo pipeline (recognition, then per-mention linking — see
    fetch_social_media_posts' ?postStatus / ?geoRecognitionStatus / ?locStatus) are
    independent stages, so a report can fail any combination of them. Each filter
    dimension is only meaningful, and only applied, on the side that's intact:
      - classification failure (processing_status in ('error', 'no_text')): category/
        relevance are absent/unreliable by construction, so eff_events/eff_relevance
        are NOT applied to these rows regardless of their geo outcome.
      - geo failure — either recognition (geo_recognition_status == 'error': the NER
        step crashed, so `locations` is empty by construction and that emptiness
        can't be trusted as "no location mentioned") or linking (geo_recognition_status
        == 'ok' but at least one location mention has a per-mention "error" status in
        the `locations` JSON, distinct from "no_candidates" which just means no place
        was found and isn't a failure): loc_filter classifies by location outcome,
        which is exactly what's broken here, so it is NOT applied to these rows
        regardless of their classification outcome.
    Each bypass is keyed only off the axis it depends on, so a row failing both
    axes at once still gets the right (skip both) treatment. Geo-failure reports
    are NOT excluded from the normal (non-issues) view — their relevance/category
    data is fine if classification succeeded, only the location is incomplete, so
    they stay visible there too; only_issues adds a second, filtered view onto the
    same reports rather than moving them out.
    """
    # Upper time bound: an explicit `until` (custom range), else "now".
    q = session.query(Report).filter(Report.timestamp <= (until or _now_utc()))

    if since is not None:
        q = q.filter(Report.timestamp > since)

    if demo_mode:
        q = q.filter(Report.identifier.like("demo-%"))
    else:
        q = q.filter(~Report.identifier.like("demo-%"))

    # The onboarding tour's example report is never part of normal browsing,
    # regardless of demo_mode — it's only ever fetched directly by identifier
    # via get_tour_example / GET /api/v1/reports/tour-example.
    q = q.filter(~Report.identifier.like("tour-example%"))

    _locs_text = cast(Report.locations, SaText)
    is_classification_failure = Report.processing_status.in_(_ISSUE_STATUSES)
    is_geo_recognition_failure = Report.geo_recognition_status == 'error'
    is_geoparsing_failure = and_(
        # NULL-safe "not a recognition failure" — plain `!= 'error'` would evaluate
        # to NULL (excluding the row) for legacy reports where the column is NULL.
        or_(Report.geo_recognition_status.is_(None), Report.geo_recognition_status != 'error'),
        _locs_text.like('%"status": "error"%'),
    )
    is_location_failure = or_(is_geo_recognition_failure, is_geoparsing_failure)

    if only_issues:
        q = q.filter(or_(is_classification_failure, is_location_failure))
    else:
        q = q.filter(
            or_(Report.processing_status.is_(None), Report.processing_status == 'ok')
        )

    if eff_platform:
        q = q.filter(
            or_(*[Report.platform.like(f"{p}%") for p in eff_platform])
        )

    if only_issues:
        # Apply event/relevance filters only where classification is intact;
        # classification-failure rows bypass them unconditionally regardless of
        # their (independent) geo outcome.
        if eff_events:
            q = q.filter(or_(
                is_classification_failure,
                Report.event_types.overlap(cast(eff_events, PG_ARRAY(String))),
            ))
        if eff_relevance:
            q = q.filter(or_(
                is_classification_failure,
                Report.relevance.in_(eff_relevance),
            ))
    else:
        if eff_events:
            q = q.filter(
                Report.event_types.overlap(cast(eff_events, PG_ARRAY(String)))
            )

        if eff_relevance:
            q = q.filter(Report.relevance.in_(eff_relevance))

    if admitted_up_to is not None:
        # Admission watermark: admitted = a prefix of ingestion (SERIAL id) order.
        q = q.filter(Report.id <= admitted_up_to)

    if search:
        term = f"%{search}%"
        q = q.filter(
            or_(Report.text.ilike(term), Report.author.ilike(term))
        )

    _ALL_LOC = frozenset({'localized', 'pending', 'unlocalized'})
    locs_text = cast(Report.locations, SaText)
    if loc_filter and set(loc_filter) < _ALL_LOC:
        _loc_set = set(loc_filter)
        conditions = []
        if 'localized' in _loc_set:
            conditions.append(locs_text.like('%"osm_id"%'))
        if 'pending' in _loc_set:
            conditions.append(and_(
                Report.locations.isnot(None),
                ~locs_text.like('%"osm_id"%'),
                locs_text != '[]',
            ))
        if 'unlocalized' in _loc_set:
            conditions.append(or_(Report.locations.is_(None), locs_text == '[]'))
        if conditions:
            loc_cond = or_(*conditions)
            # Apply the location filter only where the geo pipeline is intact; a
            # geo-failure row bypasses it unconditionally regardless of its
            # (independent) classification outcome — see is_location_failure above.
            q = q.filter(or_(is_location_failure, loc_cond) if only_issues else loc_cond)

    return q


# ---------------------------------------------------------------------------
# Display-filter predicate — THE Python-side definition of report visibility
# ---------------------------------------------------------------------------

_ALL_LOC_TYPES = frozenset({'localized', 'pending', 'unlocalized'})


def effective_loc_set(loc_filter: list[str] | None) -> set[str] | None:
    """None (no restriction) unless loc_filter is a strict subset of the three
    location types — the single place this convention is decoded."""
    return set(loc_filter) if loc_filter and set(loc_filter) < _ALL_LOC_TYPES else None


def loc_status_of(effective_locs: list) -> str:
    """'localized' | 'pending' | 'unlocalized' for a report's effective locations.
    Single Python-side definition; build_report_query's SQL CASE and the facet
    scan's _loc_status_expr are its documented SQL mirrors."""
    if any(isinstance(loc, dict) and "osm_id" in loc for loc in effective_locs):
        return 'localized'
    if effective_locs:
        return 'pending'
    return 'unlocalized'


def has_geo_linking_error(effective_locs: list) -> bool:
    """At least one location mention whose geo-linking failed outright
    ('error' — distinct from 'no_candidates', which isn't a failure)."""
    return any(isinstance(loc, dict) and loc.get('status') == 'error' for loc in effective_locs)


def passes_display_filters(
    *,
    report_id: int,
    author: str | None,
    effective_locs: list,
    geo_recognition_status: str | None,
    loc_set: set[str] | None,
    seen_ids: set[int],
    flagged_authors: set[str],
    hide_seen: bool,
    hide_flagged: bool,
    hide_unflagged: bool,
    only_issues: bool,
) -> bool:
    """The one Python-side visibility predicate, shared by the sidebar list
    (filter_by_display) and the map dots (build_dots) so the two can never
    drift apart again. It covers what SQL can't see — user-modified locations —
    while build_report_query pushes down the SQL-expressible mirror of the same
    rules.

    only_issues: loc_set is bypassed for reports that are in the Issues tab
    BECAUSE the geo pipeline (recognition or per-mention linking) failed —
    filtering those by location outcome would exclude the very reports the tab
    exists to surface. Mirrors build_report_query's is_location_failure
    handling of loc_filter."""
    if hide_seen and report_id in seen_ids:
        return False
    if hide_flagged and (author or "") in flagged_authors:
        return False
    if hide_unflagged and (author or "") not in flagged_authors:
        return False

    if loc_set:
        is_location_issue = only_issues and (
            geo_recognition_status == 'error' or has_geo_linking_error(effective_locs)
        )
        if not is_location_issue and loc_status_of(effective_locs) not in loc_set:
            return False

    return True


def filter_by_display(
    reports: list[Report],
    loc_filter: list[str] | None,
    seen_ids: set[int],
    flagged_authors: set[str],
    user_locs_map: dict[int, list],
    hide_seen: bool,
    hide_flagged: bool,
    hide_unflagged: bool,
    only_issues: bool = False,
) -> list[Report]:
    """Python-level post-query filtering — a thin loop over
    passes_display_filters (see there for the actual rules)."""
    loc_set = effective_loc_set(loc_filter)
    return [
        r
        for r in reports
        if passes_display_filters(
            report_id=r.id,
            author=r.author,
            effective_locs=(user_locs_map[r.id] if r.id in user_locs_map else r.locations) or [],
            geo_recognition_status=r.geo_recognition_status,
            loc_set=loc_set,
            seen_ids=seen_ids,
            flagged_authors=flagged_authors,
            hide_seen=hide_seen,
            hide_flagged=hide_flagged,
            hide_unflagged=hide_unflagged,
            only_issues=only_issues,
        )
    ]


def _compute_issue_kinds(report: Report) -> list[str]:
    """Which pipeline failure(s) (if any) this report represents, for display in
    the Issues tab. Empty for reports that aren't issues at all. Classification and
    the geo pipeline (recognition, then linking) are independent stages, so a report
    can carry a classification failure AND a geo failure at once — hence a list, not
    a single value. Kept in sync with build_report_query's only_issues filter."""
    kinds: list[str] = []
    if report.processing_status == 'error':
        kinds.append('classification_failed')
    elif report.processing_status == 'no_text':
        kinds.append('no_text')

    if report.geo_recognition_status == 'error':
        # Recognition failing means no mentions could have been extracted at all,
        # so `locations` is empty by construction — nothing to check per-mention.
        kinds.append('geo_recognition_failed')
    elif has_geo_linking_error(report.locations or []):
        kinds.append('geoparsing_failed')

    return kinds


# ---------------------------------------------------------------------------
# build_report_dto
# ---------------------------------------------------------------------------

def build_report_dto(
    report: Report,
    user_state_row: UserReportState | None = None,
    user_locs_map: dict[int, list] | None = None,
    seen_ids: set[int] | None = None,
    flagged_authors: set[str] | None = None,
    new_ids: set[int] | None = None,
) -> ReportDTO:
    """Build a ReportDTO from an ORM row plus optional per-user state."""
    user_locs_map = user_locs_map or {}
    seen_ids = seen_ids or set()
    flagged_authors = flagged_authors or set()
    new_ids = new_ids or set()

    effective_locs_raw = (user_locs_map[report.id] if report.id in user_locs_map else report.locations) or []
    original_locs_raw = report.original_locations or report.locations or []

    effective_locs = _coerce_locations(effective_locs_raw)
    original_locs = _coerce_locations(original_locs_raw)

    if user_state_row is not None:
        user_state = UserStateDTO(
            hide=user_state_row.hide,
            flag=user_state_row.flag,
            flag_author=user_state_row.flag_author,
            new=user_state_row.new,
            locations=(
                _coerce_locations(user_state_row.locations)
                if user_state_row.locations is not None
                else None
            ),
        )
    else:
        user_state = UserStateDTO(
            hide=report.id in seen_ids,
            flag=(report.author or "") in flagged_authors,
            new=report.id in new_ids,
        )

    return ReportDTO(
        id=report.id,
        identifier=report.identifier,
        text=report.text,
        url=report.url,
        platform=report.platform,
        timestamp=report.timestamp.replace(tzinfo=timezone.utc),
        event_types=report.event_types or [report.event_type] if report.event_type else [],
        relevance=report.relevance,
        processing_status=report.processing_status,
        geo_recognition_status=report.geo_recognition_status,
        issue_kinds=_compute_issue_kinds(report),
        author=report.author,
        locations=effective_locs,
        original_locations=original_locs,
        user_state=user_state,
    )


# ---------------------------------------------------------------------------
# get_reports
# ---------------------------------------------------------------------------

@dataclass
class ReportsResult:
    """Everything the reports/bundle endpoints need from one get_reports call.
    Named fields instead of the previous 15-tuple, whose every extension meant
    editing all return/call sites positionally in lockstep.

    The facet/platform fields are None under the lean views (only_new /
    only_issues) where the facet scan is skipped: None = "not computed, keep
    what you had", {} = a real empty result. See ReportsResponse."""
    reports: list[ReportDTO] = field(default_factory=list)
    pending_count: int = 0
    loaded_at: str = ""
    event_type_totals: dict[str, int] | None = None
    all_platforms: list[str] | None = None
    platform_counts: dict[str, int] | None = None
    platform_added_counts: dict[str, int] | None = None
    relevance_totals: dict[str, int] | None = None
    location_counts: dict[str, int] | None = None
    has_more: bool = False
    total_count: int = 0
    unseen_count: int = 0
    processing_status_totals: dict[str, int] = field(default_factory=dict)
    reports_total_count: int = 0
    reports_unseen_count: int = 0


def get_reports(
    session: Session,
    username: str,
    loc_filter: list[str] | None = None,
    platforms: list[str] | None = None,
    event_types: list[str] | None = None,
    relevances: list[str] | None = None,
    show_hidden: bool = False,
    show_flagged: bool = True,
    show_unflagged: bool = True,
    demo_mode: bool = False,
    limit: int = 50,
    search: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    only_new: bool = False,
    only_issues: bool = False,
) -> ReportsResult:
    """
    pending_count = number of reports in DB that have not yet been admitted.
    only_new restricts the returned list (and total_count) to reports still marked
    new, so the sidebar's "only new" view is correctly paginated server-side rather
    than filtered after the fact over the loaded page. Facet/pending counts are left
    at the full distribution.
    only_issues switches to the "extraction issues" tab: reports whose pipeline
    failed (processing_status in error/no_text), with event_type/relevance filters
    ignored (see build_report_query). Mutually exclusive with only_new in practice
    (the frontend only sends one), but both are independently honored here.
    """
    user_state = get_user_state(username, session)
    seen_ids = user_state.hidden_ids
    flagged_authors = user_state.flagged_authors
    user_locs_map = user_state.locs_map
    watermark = user_state.admitted_up_to
    acknowledged_ids = user_state.acknowledged_ids

    eff_platform, eff_events, eff_relevance = normalize_filters(
        platforms, event_types, relevances
    )

    # Author-visibility filter (show_flagged/show_unflagged), applied to both badge
    # queries below to match filter_by_display's semantics exactly — otherwise the
    # badges silently ignore these two toggles while the actual lists (which DO go
    # through filter_by_display) honor them, producing a badge that doesn't match
    # what switching tabs would actually show. `Report.id.is_(None)` is a portable
    # "match nothing" (id is a non-null PK), used instead of sqlalchemy.false() for
    # the "both toggles off" / "no author ever flagged" edge cases.
    def _apply_author_visibility(bq):
        if show_flagged and show_unflagged:
            return bq
        if not show_flagged and not show_unflagged:
            return bq.filter(Report.id.is_(None))
        # Coalesce to '' like filter_by_display's `r.author or ""` — a NULL author
        # would otherwise make `~author.in_(...)` evaluate to NULL (row excluded)
        # instead of the correct "definitely not a flagged author" TRUE.
        _author = func.coalesce(Report.author, '')
        if not show_flagged:
            return bq.filter(~_author.in_(flagged_authors)) if flagged_authors else bq
        # not show_unflagged
        return bq.filter(_author.in_(flagged_authors)) if flagged_authors else bq.filter(Report.id.is_(None))

    # Reports still marked hidden (show_hidden=False, the default) are excluded the
    # same way filter_by_display excludes them from the actual list.
    _hidden_ids = set() if show_hidden else seen_ids

    # Issue-kind facet — grouped count, always computed (independent of only_issues)
    # so the "Issues (N)" tab badge stays accurate while on the Reports tab, and
    # reflects the SAME active platform/event/relevance/loc/search/hide/flag filters
    # as the Issues list itself would (build_report_query already encodes the
    # correct per-issue-kind bypass rules for eff_events/eff_relevance/loc_filter,
    # so this is just the issues-view query with a GROUP BY instead of a LIMIT).
    # Bucket priority mirrors _compute_issue_kinds; a row could technically qualify
    # for more than one bucket (classification and geo fail independently) but this
    # single-bucket grouping is only used for the summary breakdown, not for which
    # rows show up — see build_report_query for that.
    _issue_kind_expr = case(
        (Report.processing_status == 'error', 'classification_failed'),
        (Report.processing_status == 'no_text', 'no_text'),
        (Report.geo_recognition_status == 'error', 'geo_recognition_failed'),
        else_='geoparsing_failed',
    )
    _issues_badge_q = _apply_author_visibility(
        build_report_query(
            session, since=since, until=until, demo_mode=demo_mode, only_issues=True,
            eff_platform=eff_platform, eff_events=eff_events, eff_relevance=eff_relevance,
            loc_filter=loc_filter, search=search,
        )
    )
    if _hidden_ids:
        _issues_badge_q = _issues_badge_q.filter(~Report.id.in_(_hidden_ids))
    processing_status_totals: dict[str, int] = {}
    for (kind, count) in (
        _issues_badge_q
        .with_entities(_issue_kind_expr, func.count())
        .group_by(_issue_kind_expr)
        .all()
    ):
        if kind:
            processing_status_totals[kind] = count

    # Reports-tab pill — total admitted reports matching filters, always computed
    # (mirrors processing_status_totals above) so it stays informative while the
    # Issues tab is active, same as the Issues pill stays informative while on
    # Reports. This is the Reports-view counterpart to processing_status_totals'
    # sum: a plain total, not an unseen-only count — the two pills are meant to be
    # directly comparable ("how much is in each tab"), and the header (computed by
    # the caller) combines this with reports_unseen_count and the issues total for
    # its own two numbers. Applies the same active filters as the Reports list
    # itself (a single indexed COUNT, cheap enough to run unconditionally).
    _reports_total_q = _apply_author_visibility(
        build_report_query(
            session, since=since, until=until, demo_mode=demo_mode,
            eff_platform=eff_platform, eff_events=eff_events, eff_relevance=eff_relevance,
            loc_filter=loc_filter, search=search,
            admitted_up_to=watermark,
        )
    )
    if _hidden_ids:
        _reports_total_q = _reports_total_q.filter(~Report.id.in_(_hidden_ids))
    reports_total_count = _reports_total_q.count()

    # Reports-view unseen count — same query, restricted to still-new reports
    # (admitted but not acknowledged, not hidden). Feeds the header's combined
    # red badge (see the router/frontend), which adds this to the Issues total:
    # Issues has no seen/unseen distinction (every matching failure is
    # "actionable" regardless of whether you've looked at it before), so from
    # the header's point of view the whole Issues total behaves like "unseen".
    _reports_unseen_q = _apply_author_visibility(
        build_report_query(
            session, since=since, until=until, demo_mode=demo_mode,
            eff_platform=eff_platform, eff_events=eff_events, eff_relevance=eff_relevance,
            loc_filter=loc_filter, search=search,
            admitted_up_to=watermark,
        )
    )
    _not_new_ids = acknowledged_ids | _hidden_ids
    if _not_new_ids:
        _reports_unseen_q = _reports_unseen_q.filter(~Report.id.in_(_not_new_ids))
    reports_unseen_count = _reports_unseen_q.count()

    # NOTE: under only_issues, loc_filter is still meaningful — it just doesn't apply
    # to geo-failure rows (passes_display_filters bypasses it for those; see there
    # and build_report_query's is_location_failure for the full rationale).
    _eff_loc = effective_loc_set(loc_filter)

    # Facets stay None under the lean views (see ReportsResult) — the skipped
    # scan is now an explicit "not computed" in the contract, not zeros the
    # client has to know to ignore.
    lean_view = only_new or only_issues
    event_type_totals: dict[str, int] | None = None
    platform_counts: dict[str, int] | None = None
    relevance_totals: dict[str, int] | None = None
    location_counts: dict[str, int] | None = None
    all_platforms: list[str] | None = None
    platform_added_counts: dict[str, int] | None = None
    # Unseen badge count. Under lean views we skip the full facet scan below and
    # instead set unseen_count = total_count afterwards — the returned list IS
    # the new/issues set.
    unseen_count = 0

    # Cross-filtered facet counts (option B):
    # Each dimension's count reflects all OTHER active filters but not itself,
    # so the numbers tell you "how many results does this value add to my view".
    # One query with no facet filters; cross-filtering is done in Python to keep
    # DB round trips to a minimum. Skipped entirely under lean views (the
    # expensive full-set scan); event_type/relevance facets are meaningless under
    # only_issues anyway (see build_report_query).
    if not lean_view:
        event_type_totals = {}
        platform_counts = {p: 0 for p in ALL_PLATFORMS}
        relevance_totals = {}
        location_counts = {"localized": 0, "pending": 0, "unlocalized": 0}
        _locs_text = cast(Report.locations, SaText)
        _loc_status_expr = case(
            (_locs_text.like('%"osm_id"%'), "localized"),
            (
                and_(Report.locations.isnot(None), _locs_text != "[]"),
                "pending",
            ),
            else_="unlocalized",
        )
        all_base_rows = build_report_query(
            session,
            since=since,
            until=until,
            eff_platform=None,
            eff_events=None,
            eff_relevance=None,
            demo_mode=demo_mode,
            search=search,
        ).with_entities(
            Report.id, Report.event_types, Report.platform, Report.relevance,
            Report.author, _loc_status_expr,
        ).all()

        for (rid, ets, plat, rel, row_author, loc_status) in all_base_rows:
            if not show_hidden and rid in seen_ids:
                continue
            _author = row_author or ""
            if not show_flagged and _author in flagged_authors:
                continue
            if not show_unflagged and _author not in flagged_authors:
                continue

            _passes_plat = eff_platform is None or (
                plat is not None and any(plat.startswith(p) for p in eff_platform)
            )
            _passes_evt = eff_events is None or bool(set(ets or []) & set(eff_events))
            _passes_rel = eff_relevance is None or rel in eff_relevance
            _passes_loc = _eff_loc is None or loc_status in _eff_loc

            # Event type counts: apply platform + relevance + loc (not event type filter)
            if _passes_plat and _passes_rel and _passes_loc:
                for et in (ets or []):
                    event_type_totals[et] = event_type_totals.get(et, 0) + 1

            # Relevance counts: apply platform + event type + loc (not relevance filter)
            if _passes_plat and _passes_evt and _passes_loc:
                if rel:
                    relevance_totals[rel] = relevance_totals.get(rel, 0) + 1

            # Platform counts: apply event type + relevance + loc (not platform filter)
            if _passes_evt and _passes_rel and _passes_loc:
                if plat:
                    platform_counts[plat] = platform_counts.get(plat, 0) + 1

            # Location counts: apply all other filters but NOT loc — show full distribution
            if _passes_plat and _passes_evt and _passes_rel:
                location_counts[loc_status] = location_counts.get(loc_status, 0) + 1

            # Unseen badge count: every report that passes the active filters, is
            # still new (admitted under the watermark, not acknowledged), and not
            # hidden.
            if (
                user_state.is_new(rid)
                and rid not in seen_ids
                and _passes_plat and _passes_evt and _passes_rel and _passes_loc
            ):
                unseen_count += 1

        all_platforms = sorted(platform_counts.keys())

    # Count admitted posts per platform (ignoring event_type / platform filters).
    if not lean_view:
        platform_added_counts = {p: 0 for p in ALL_PLATFORMS}
        if watermark:
            added_rows = (
                build_report_query(
                    session,
                    since=since,
                    until=until,
                    admitted_up_to=watermark,
                    eff_platform=None,
                    eff_events=None,
                    eff_relevance=eff_relevance,
                    demo_mode=demo_mode,
                )
                .with_entities(Report.platform)
                .all()
            )
            for (plat,) in added_rows:
                if plat:
                    platform_added_counts[plat] = platform_added_counts.get(plat, 0) + 1

    # If the sidebar is empty (nothing admitted yet), return [] and count pending.
    # only_issues bypasses admission entirely — it's a diagnostic view over every
    # matching failed report, not a per-user curated inbox, so there's nothing to
    # "admit" and this early-return must not apply to it.
    if not watermark and not only_issues:
        pending_q = build_report_query(
            session,
            since=since,
            until=until,
            eff_platform=eff_platform,
            eff_events=eff_events,
            eff_relevance=eff_relevance,
            demo_mode=demo_mode,
            loc_filter=loc_filter,
            only_issues=only_issues,
        )
        pending_count = pending_q.count()
        loaded_at = datetime.now(timezone.utc).isoformat()
        return ReportsResult(
            pending_count=pending_count,
            loaded_at=loaded_at,
            event_type_totals=event_type_totals,
            all_platforms=all_platforms,
            platform_counts=platform_counts,
            platform_added_counts=platform_added_counts,
            relevance_totals=relevance_totals,
            location_counts=location_counts,
            unseen_count=unseen_count,
            processing_status_totals=processing_status_totals,
            reports_total_count=reports_total_count,
            reports_unseen_count=reports_unseen_count,
        )

    # Build the main query (only admitted reports — except only_issues, which
    # shows every matching report regardless of admission state)
    q = build_report_query(
        session,
        since=since,
        until=until,
        admitted_up_to=None if only_issues else watermark,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        demo_mode=demo_mode,
        search=search,
        only_issues=only_issues,
    )

    # "Only new" view: restrict to reports still marked new (admitted but not
    # acknowledged) so the page (and its total_count) contains the new reports
    # directly instead of relying on the client to filter the loaded page.
    if only_new and acknowledged_ids:
        q = q.filter(~Report.id.in_(acknowledged_ids))

    # Python-level display filtering
    hide_seen = not show_hidden
    hide_flagged = not show_flagged
    hide_unflagged = not show_unflagged

    # When nothing would be filtered in Python and loc_filter='all', push LIMIT into
    # SQL so we only load page_size ORM objects instead of every admitted report.
    can_push_limit = (
        not hide_seen
        and not hide_flagged
        and not hide_unflagged
        and not _eff_loc
    )

    if can_push_limit:
        total_count = q.count()
        has_more = total_count > limit
        filtered: list[Report] = q.order_by(Report.timestamp.desc()).limit(limit).all()
    else:
        reports_orm: list[Report] = q.order_by(Report.timestamp.desc()).all()
        filtered = filter_by_display(
            reports_orm,
            loc_filter=loc_filter,
            seen_ids=seen_ids,
            flagged_authors=flagged_authors,
            user_locs_map=user_locs_map,
            hide_seen=hide_seen,
            hide_flagged=hide_flagged,
            hide_unflagged=hide_unflagged,
            only_issues=only_issues,
        )
        total_count = len(filtered)
        has_more = total_count > limit
        filtered = filtered[:limit]

    # Build a quick lookup: report_id → UserReportState row
    user_state_rows: dict[int, UserReportState] = {
        row.report_id: row
        for row in session.query(UserReportState).filter(
            UserReportState.username == username,
            UserReportState.report_id.in_([r.id for r in filtered]),
        ).all()
    }

    # Page-scoped "new" set for the DTOs (derived from the watermark — see
    # UserState.is_new), instead of materializing newness for every admitted
    # report.
    page_new_ids = {r.id for r in filtered if user_state.is_new(r.id)}
    dtos = [
        build_report_dto(
            r,
            user_state_row=user_state_rows.get(r.id),
            user_locs_map=user_locs_map,
            seen_ids=seen_ids,
            flagged_authors=flagged_authors,
            new_ids=page_new_ids,
        )
        for r in filtered
    ]

    # Pending count = reports that match filters (incl. loc_filter and the active
    # time window) but are NOT yet admitted — with the watermark model this is a
    # plain range condition, no join. Always computed against the REPORTS view
    # (only_issues=False), even when the Issues tab is active: admission is a
    # Reports-view concept, and the auto-update poll relies on this number to
    # decide when to admit — hardcoding it to 0 under only_issues (as before)
    # silently paused auto-admission for as long as the Issues tab stayed open,
    # letting new reports pile up un-admitted.
    pending_count = (
        build_report_query(
            session,
            since=since,
            until=until,
            eff_platform=eff_platform,
            eff_events=eff_events,
            eff_relevance=eff_relevance,
            demo_mode=demo_mode,
            loc_filter=loc_filter,
        )
        .filter(Report.id > watermark)
        .count()
    )

    # Under only_new/only_issues the facet scan (which normally computes unseen_count)
    # was skipped; the returned list is exactly the matching set, so total_count is the badge.
    if lean_view:
        unseen_count = total_count

    loaded_at = datetime.now(timezone.utc).isoformat()
    return ReportsResult(
        reports=dtos,
        pending_count=pending_count,
        loaded_at=loaded_at,
        event_type_totals=event_type_totals,
        all_platforms=all_platforms,
        platform_counts=platform_counts,
        platform_added_counts=platform_added_counts,
        relevance_totals=relevance_totals,
        location_counts=location_counts,
        has_more=has_more,
        total_count=total_count,
        unseen_count=unseen_count,
        processing_status_totals=processing_status_totals,
        reports_total_count=reports_total_count,
        reports_unseen_count=reports_unseen_count,
    )


# ---------------------------------------------------------------------------
# get_tour_example
# ---------------------------------------------------------------------------

def get_tour_example(session: Session, username: str) -> ReportDTO:
    """
    Fetch the permanent onboarding-tour example report (seeded once at startup —
    see main.py::_init_db), admitting it for `username` so hide/flag/acknowledge/
    location-edit all work exactly like a real report — no special-casing needed
    anywhere else. Its timestamp is refreshed to "now" on every fetch so it always
    reads as a recent post, and its per-user state is reset to defaults (not
    hidden/flagged, both locations restored) so a tour replay — or someone else's
    tour, if hide/flag ever leaked to a shared demo environment — always starts
    from the same clean demo, regardless of what a previous run clicked. Raises
    LookupError if the seed is somehow missing (the router turns that into a
    404 rather than silently returning nothing).
    """
    report: Report | None = (
        session.query(Report).filter(Report.identifier == "tour-example").first()
    )
    if report is None:
        raise LookupError("tour-example report is not seeded")

    report.timestamp = _now_utc()
    session.commit()

    # No admission needed: the example is excluded from every list query by its
    # identifier, is fetched directly, and its DTO's flags come from the user
    # state row upserted here (reset to defaults so a tour replay starts clean).
    upsert_user_state(
        username, report.id, session,
        hide=False, flag=False, flag_author=None, new=True, locations=None,
    )

    user_state_row = (
        session.query(UserReportState)
        .filter(
            UserReportState.username == username,
            UserReportState.report_id == report.id,
        )
        .first()
    )

    return build_report_dto(report, user_state_row=user_state_row)


# ---------------------------------------------------------------------------
# get_new_count
# ---------------------------------------------------------------------------

def get_new_count(
    session: Session,
    username: str,
    since_iso: str,
    eff_platform: list[str] | None,
    eff_events: list[str] | None,
    eff_relevance: list[str] | None,
    loc_filter: list[str] | None,
    show_hidden: bool,
    show_flagged: bool,
    show_unflagged: bool,
    demo_mode: bool,
) -> int:
    """Count reports newer than since_iso that are not yet admitted."""
    try:
        since = datetime.fromisoformat(since_iso.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except (ValueError, AttributeError):
        since = _now_utc()

    user_state = get_user_state(username, session)

    return (
        build_report_query(
            session,
            since=since,
            eff_platform=eff_platform,
            eff_events=eff_events,
            eff_relevance=eff_relevance,
            demo_mode=demo_mode,
        )
        .filter(Report.id > user_state.admitted_up_to)
        .count()
    )


# ---------------------------------------------------------------------------
# toggle_hide
# ---------------------------------------------------------------------------

def toggle_hide(
    session: Session,
    username: str,
    report_id: int,
    hide: bool,
) -> None:
    upsert_user_state(username, report_id, session, hide=hide)


# ---------------------------------------------------------------------------
# toggle_flag
# ---------------------------------------------------------------------------

def toggle_flag(
    session: Session,
    username: str,
    author: str,
    flag: bool,
) -> int:
    """Flag (or un-flag) all reports by the given author. Returns affected count."""
    report_ids: list[int] = [
        row[0]
        for row in session.query(Report.id).filter(Report.author == author).all()
    ]
    if not report_ids:
        return 0

    # Single multi-row upsert with one commit — the previous per-report
    # upsert_user_state loop committed once per report, so flagging a prolific
    # author meant hundreds of sequential round trips.
    stmt = pg_insert(UserReportState).values([
        {
            "username": username,
            "report_id": rid,
            "flag": flag,
            "flag_author": author if flag else None,
        }
        for rid in report_ids
    ])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_report",
        set_={
            "flag": stmt.excluded.flag,
            "flag_author": stmt.excluded.flag_author,
        },
    )
    session.execute(stmt)
    session.commit()

    return len(report_ids)


# ---------------------------------------------------------------------------
# acknowledge_report
# ---------------------------------------------------------------------------

def acknowledge_report(
    session: Session,
    username: str,
    report_id: int,
) -> None:
    upsert_user_state(username, report_id, session, new=False)


# ---------------------------------------------------------------------------
# update_locations
# ---------------------------------------------------------------------------

def update_locations(
    session: Session,
    username: str,
    report_id: int,
    locations: list[dict],
) -> None:
    upsert_user_state(username, report_id, session, locations=locations)


# ---------------------------------------------------------------------------
# restore_locations
# ---------------------------------------------------------------------------

def restore_locations(
    session: Session,
    username: str,
    report_id: int,
) -> None:
    upsert_user_state(username, report_id, session, locations=None)


# ---------------------------------------------------------------------------
# build_dots
# ---------------------------------------------------------------------------

def build_dots(
    session: Session,
    username: str,
    eff_platform: list[str] | None,
    eff_events: list[str] | None,
    eff_relevance: list[str] | None,
    loc_filter: list[str] | None,
    show_hidden: bool,
    show_flagged: bool,
    show_unflagged: bool,
    demo_mode: bool,
    search: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    only_new: bool = False,
    only_issues: bool = False,
) -> list[dict]:
    """
    Build the list of map-dot dicts from admitted reports that have coordinates.
    only_new restricts to reports still marked new (mirrors get_reports) so the map
    matches the "only new" sidebar view. only_issues mirrors get_reports likewise —
    see build_report_query for why event_type/relevance filters don't apply there.
    """
    user_state = get_user_state(username, session)
    seen_ids = user_state.hidden_ids
    flagged_authors = user_state.flagged_authors
    user_locs_map = user_state.locs_map
    watermark = user_state.admitted_up_to

    if not watermark and not only_issues:
        return []

    q = build_report_query(
        session,
        since=since,
        until=until,
        admitted_up_to=None if only_issues else watermark,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        demo_mode=demo_mode,
        search=search,
        only_issues=only_issues,
    )

    if only_new and user_state.acknowledged_ids:
        q = q.filter(~Report.id.in_(user_state.acknowledged_ids))

    # Unlike get_reports, dots never surface hidden reports on the map — show_hidden
    # only lets the sidebar list display them (greyed out), it doesn't apply here.
    hide_seen = True
    hide_flagged = not show_flagged
    hide_unflagged = not show_unflagged

    # Display filtering is the SAME shared predicate the sidebar list uses
    # (passes_display_filters) — dots and list can't drift apart. Applied in
    # Python so it respects user-modified locations from user_locs_map.
    _loc_set = effective_loc_set(loc_filter)

    rows = q.with_entities(
        Report.id,
        Report.text,
        Report.author,
        Report.platform,
        Report.timestamp,
        Report.event_types,
        Report.event_type,
        Report.relevance,
        Report.url,
        Report.locations,
        Report.geo_recognition_status,
    ).order_by(Report.timestamp.desc()).all()

    # Precompute bbox for every unique (osm_id, osm_type) referenced across all rows.
    # This restores containment-suppression for dots after polygon was moved out of locations.
    osm_keys: set[tuple[str, str]] = set()
    for row in rows:
        for loc in (row[9] or []):
            if isinstance(loc, dict) and loc.get("osm_id") and loc.get("osm_type"):
                osm_keys.add((str(loc["osm_id"]), str(loc["osm_type"])))
    bbox_map: dict[tuple[str, str], list[float]] = {}
    if osm_keys:
        for pr in _query_location_polygons(session, osm_keys):
            if isinstance(pr.polygon, dict):
                bb = _polygon_bbox(pr.polygon)
                if bb:
                    bbox_map[(pr.osm_id, pr.osm_type)] = bb

    dots: list[dict] = []
    for (rid, text, author, platform, timestamp, event_types, event_type, relevance, url, locs_raw, geo_status) in rows:
        effective_locs: list = (user_locs_map[rid] if rid in user_locs_map else locs_raw) or []

        if not passes_display_filters(
            report_id=rid,
            author=author,
            effective_locs=effective_locs,
            geo_recognition_status=geo_status,
            loc_set=_loc_set,
            seen_ids=seen_ids,
            flagged_authors=flagged_authors,
            hide_seen=hide_seen,
            hide_flagged=hide_flagged,
            hide_unflagged=hide_unflagged,
            only_issues=only_issues,
        ):
            continue

        for loc in effective_locs:
            if not isinstance(loc, dict):
                continue
            lat = loc.get("lat")
            lon = loc.get("lon")
            if lat is None or lon is None:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (TypeError, ValueError):
                continue

            loc_bbox_area: float | None = None
            loc_bbox: list[float] | None = None
            # Prefer polygon bbox from location_polygons (reflects full geographic extent,
            # e.g. a railway route spanning multiple cities). Fall back to Nominatim
            # boundingbox which may only cover the geocoded result's centroid area.
            if loc.get("osm_id") and loc.get("osm_type"):
                bb = _best_polygon(bbox_map, str(loc["osm_id"]), str(loc["osm_type"]))
                if bb:
                    min_lat, max_lat, min_lon, max_lon = bb
                    loc_bbox_area = (max_lat - min_lat) * (max_lon - min_lon)
                    loc_bbox = bb
            if loc_bbox is None:
                bbox = loc.get("boundingbox")
                if bbox and len(bbox) == 4:
                    try:
                        min_lat, max_lat, min_lon, max_lon = map(float, bbox)
                        loc_bbox_area = (max_lat - min_lat) * (max_lon - min_lon)
                        loc_bbox = [min_lat, max_lat, min_lon, max_lon]
                    except (TypeError, ValueError):
                        pass

            dots.append(
                {
                    "report_id": rid,
                    "lat": lat_f,
                    "lon": lon_f,
                    "seen": rid in seen_ids,
                    "hide": rid in seen_ids,
                    "flag": (author or "") in flagged_authors,
                    "new": user_state.is_new(rid),
                    "location_name": loc.get("name") or loc.get("display_name") or "",
                    "location_display": loc.get("mention") or "",
                    "text": (text or "")[:300],
                    "author": author or "",
                    "platform": platform,
                    "timestamp": timestamp.replace(tzinfo=timezone.utc).isoformat(),
                    "event_types": event_types or ([event_type] if event_type else []),
                    "relevance": relevance,
                    "url": url,
                    "location_bbox_area": loc_bbox_area,
                    "location_bbox": loc_bbox,
                }
            )

    return dots
