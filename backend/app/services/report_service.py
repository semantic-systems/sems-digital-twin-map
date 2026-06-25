from __future__ import annotations

"""
report_service.py
-----------------
All business logic for the /api/v1/reports endpoints.
Ports the equivalent Dash-callback logic from src/app/layout/map/map.py
and src/app/layout/map/sidebar.py into plain functions that accept a
SQLAlchemy Session and return plain Python / Pydantic objects.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import String, cast, case, and_, or_
from sqlalchemy import Text as SaText
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..db import LocationPolygon, Report, UserReportState
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
    from sqlalchemy import tuple_

    base_keys: set[tuple[str, str]] = {
        (str(loc["osm_id"]), str(loc["osm_type"]))
        for loc in locations
        if isinstance(loc, dict) and loc.get("osm_id") and loc.get("osm_type")
    }
    if not base_keys:
        return locations

    rows = (
        session.query(LocationPolygon)
        .filter(tuple_(LocationPolygon.osm_id, LocationPolygon.osm_type).in_(
            _osm_keys_with_alts(base_keys)
        ))
        .all()
    )
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

def get_user_state(
    username: str,
    session: Session,
) -> tuple[set[int], set[str], dict[int, list], set[int], set[int], dict[str, dict]]:
    """
    Returns:
        seen_ids        – report_ids where hide=True
        flagged_authors – set of flag_author strings where flag=True
        user_locs_map   – {report_id: locations} where locations IS NOT NULL
        added_ids       – report_ids where first_seen_at IS NOT NULL
        new_ids         – report_ids where first_seen_at IS NOT NULL AND new=True
        snapshot        – {str(report_id): {hide, flag, flag_author, added, new, author}}
    """
    rows: list[UserReportState] = (
        session.query(UserReportState)
        .filter(UserReportState.username == username)
        .all()
    )

    seen_ids: set[int] = set()
    flagged_authors: set[str] = set()
    user_locs_map: dict[int, list] = {}
    added_ids: set[int] = set()
    new_ids: set[int] = set()
    snapshot: dict[str, dict] = {}

    for row in rows:
        rid = row.report_id
        if row.hide:
            seen_ids.add(rid)
        if row.flag and row.flag_author:
            flagged_authors.add(row.flag_author)
        if row.locations is not None:
            user_locs_map[rid] = row.locations
        if row.first_seen_at is not None:
            added_ids.add(rid)
            if row.new:
                new_ids.add(rid)
        snapshot[str(rid)] = {
            "hide": row.hide,
            "flag": row.flag,
            "flag_author": row.flag_author,
            "added": row.first_seen_at is not None,
            "new": row.new,
            "author": row.flag_author,
        }

    return seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot


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
# bulk_admit_reports
# ---------------------------------------------------------------------------

def bulk_admit_reports(
    username: str,
    report_ids: list[int],
    session: Session,
) -> list[int]:
    """
    Upsert first_seen_at = now() for all given report IDs.
    If the row already exists, first_seen_at is only updated when it is
    currently NULL (COALESCE preserves an existing timestamp).
    hide and flag are never overwritten on conflict.
    Returns the list of IDs that were actually processed.
    """
    if not report_ids:
        return []

    # Filter to IDs that actually exist in the reports table
    existing_ids: list[int] = [
        row[0]
        for row in session.query(Report.id)
        .filter(Report.id.in_(report_ids))
        .all()
    ]
    if not existing_ids:
        return []

    now = _now_utc()

    from sqlalchemy import func

    for rid in existing_ids:
        stmt = pg_insert(UserReportState).values(
            username=username,
            report_id=rid,
            hide=False,
            flag=False,
            first_seen_at=now,
            new=True,
        )
        # On conflict: preserve existing first_seen_at if already set;
        # do NOT overwrite hide or flag so user choices are retained.
        stmt = stmt.on_conflict_do_update(
            constraint="uq_user_report",
            set_={
                "first_seen_at": func.coalesce(
                    UserReportState.__table__.c.first_seen_at,
                    stmt.excluded.first_seen_at,
                ),
            },
        )
        session.execute(stmt)

    session.commit()
    return existing_ids


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

def build_report_query(
    session: Session,
    since: datetime | None = None,
    until: datetime | None = None,
    added_ids: set[int] | None = None,
    eff_platform: list[str] | None = None,
    eff_events: list[str] | None = None,
    eff_relevance: list[str] | None = None,
    demo_mode: bool = False,
    search: str | None = None,
    loc_filter: list[str] | None = None,
):
    """
    Returns a SQLAlchemy Query[Report] with all filters applied.
    Does NOT call .all() — callers may add further ordering / limits.
    loc_filter: None or all three values means no restriction; a strict subset
    filters to reports matching any of the listed location types.
    """
    # Upper time bound: an explicit `until` (custom range), else "now".
    q = session.query(Report).filter(Report.timestamp <= (until or _now_utc()))

    if since is not None:
        q = q.filter(Report.timestamp > since)

    if demo_mode:
        q = q.filter(Report.identifier.like("demo-%"))
    else:
        q = q.filter(~Report.identifier.like("demo-%"))

    if eff_platform:
        q = q.filter(
            or_(*[Report.platform.like(f"{p}%") for p in eff_platform])
        )

    if eff_events:
        q = q.filter(
            Report.event_types.overlap(cast(eff_events, PG_ARRAY(String)))
        )

    if eff_relevance:
        q = q.filter(Report.relevance.in_(eff_relevance))

    if added_ids is not None:
        q = q.filter(Report.id.in_(added_ids))

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
            q = q.filter(or_(*conditions))

    return q


# ---------------------------------------------------------------------------
# filter_by_display
# ---------------------------------------------------------------------------

def filter_by_display(
    reports: list[Report],
    loc_filter: list[str] | None,
    seen_ids: set[int],
    flagged_authors: set[str],
    user_locs_map: dict[int, list],
    hide_seen: bool,
    hide_flagged: bool,
    hide_unflagged: bool,
) -> list[Report]:
    """Python-level post-query filtering (handles user-modified locations)."""
    _ALL_LOC = frozenset({'localized', 'pending', 'unlocalized'})
    _loc_set = set(loc_filter) if loc_filter and set(loc_filter) < _ALL_LOC else None

    result: list[Report] = []

    for r in reports:
        if hide_seen and r.id in seen_ids:
            continue
        if hide_flagged and (r.author or "") in flagged_authors:
            continue
        if hide_unflagged and (r.author or "") not in flagged_authors:
            continue

        if _loc_set:
            effective_locs: list = (user_locs_map[r.id] if r.id in user_locs_map else r.locations) or []
            is_localized = any(
                isinstance(loc, dict) and "osm_id" in loc for loc in effective_locs
            )
            has_pending = (not is_localized) and bool(effective_locs)
            is_unlocalized = not is_localized and not has_pending
            if not (
                (is_localized and 'localized' in _loc_set)
                or (has_pending and 'pending' in _loc_set)
                or (is_unlocalized and 'unlocalized' in _loc_set)
            ):
                continue

        result.append(r)

    return result


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
        author=report.author,
        locations=effective_locs,
        original_locations=original_locs,
        user_state=user_state,
    )


# ---------------------------------------------------------------------------
# get_reports
# ---------------------------------------------------------------------------

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
) -> tuple[list[ReportDTO], int, str, dict[str, int], list[str]]:
    """
    Returns (reports, pending_count, loaded_at_iso).
    pending_count = number of reports in DB that have not yet been admitted.
    """
    (
        seen_ids,
        flagged_authors,
        user_locs_map,
        added_ids,
        new_ids,
        _snapshot,
    ) = get_user_state(username, session)

    eff_platform, eff_events, eff_relevance = normalize_filters(
        platforms, event_types, relevances
    )

    # Cross-filtered facet counts (option B):
    # Each dimension's count reflects all OTHER active filters but not itself,
    # so the numbers tell you "how many results does this value add to my view".
    # One query with no facet filters; cross-filtering is done in Python to keep
    # DB round trips to a minimum.
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

    _ALL_LOC_TYPES = frozenset({'localized', 'pending', 'unlocalized'})
    _eff_loc = set(loc_filter) if (loc_filter and set(loc_filter) < _ALL_LOC_TYPES) else None

    event_type_totals: dict[str, int] = {}
    platform_counts: dict[str, int] = {p: 0 for p in ALL_PLATFORMS}
    relevance_totals: dict[str, int] = {}
    location_counts: dict[str, int] = {"localized": 0, "pending": 0, "unlocalized": 0}

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

    all_platforms = sorted(platform_counts.keys())

    # Count admitted posts per platform (ignoring event_type / platform filters).
    platform_added_counts: dict[str, int] = {p: 0 for p in ALL_PLATFORMS}
    if added_ids:
        added_rows = (
            build_report_query(
                session,
                since=since,
                until=until,
                added_ids=added_ids,
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

    # If the sidebar is empty (no admitted reports), return [] and count pending
    if not added_ids:
        pending_q = build_report_query(
            session,
            since=since,
            until=until,
            eff_platform=eff_platform,
            eff_events=eff_events,
            eff_relevance=eff_relevance,
            demo_mode=demo_mode,
            loc_filter=loc_filter,
        )
        pending_count = pending_q.count()
        loaded_at = datetime.now(timezone.utc).isoformat()
        return [], pending_count, loaded_at, event_type_totals, all_platforms, platform_counts, platform_added_counts, relevance_totals, location_counts, False, 0

    # Build the main query (only admitted reports)
    q = build_report_query(
        session,
        since=since,
        until=until,
        added_ids=added_ids,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        demo_mode=demo_mode,
        search=search,
    )

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

    dtos = [
        build_report_dto(
            r,
            user_state_row=user_state_rows.get(r.id),
            user_locs_map=user_locs_map,
            seen_ids=seen_ids,
            flagged_authors=flagged_authors,
            new_ids=new_ids,
        )
        for r in filtered
    ]

    # Pending count = reports that match filters (incl. loc_filter) but are NOT yet admitted
    all_matching_ids: set[int] = {
        row[0]
        for row in build_report_query(
            session,
            eff_platform=eff_platform,
            eff_events=eff_events,
            eff_relevance=eff_relevance,
            demo_mode=demo_mode,
            loc_filter=loc_filter,
        )
        .with_entities(Report.id)
        .all()
    }
    pending_count = len(all_matching_ids - added_ids)

    loaded_at = datetime.now(timezone.utc).isoformat()
    return dtos, pending_count, loaded_at, event_type_totals, all_platforms, platform_counts, platform_added_counts, relevance_totals, location_counts, has_more, total_count


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

    _seen_ids, _flagged_authors, _user_locs_map, added_ids, _new_ids, _ = (
        get_user_state(username, session)
    )

    q = build_report_query(
        session,
        since=since,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        demo_mode=demo_mode,
    )

    new_ids_in_db: list[int] = [row[0] for row in q.with_entities(Report.id).all()]
    # Only count those NOT already admitted
    unadmitted = [rid for rid in new_ids_in_db if rid not in added_ids]
    return len(unadmitted)


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

    for rid in report_ids:
        upsert_user_state(
            username,
            rid,
            session,
            flag=flag,
            flag_author=author if flag else None,
        )

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
    added_ids: set[int] | None = None,
    search: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict]:
    """
    Build the list of map-dot dicts from admitted reports that have coordinates.
    """
    (
        seen_ids,
        flagged_authors,
        user_locs_map,
        user_added_ids,
        new_ids,
        _snapshot,
    ) = get_user_state(username, session)

    effective_added = added_ids if added_ids is not None else user_added_ids

    if not effective_added:
        return []

    q = build_report_query(
        session,
        since=since,
        until=until,
        added_ids=effective_added,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        demo_mode=demo_mode,
        search=search,
    )

    hide_seen = not show_hidden
    hide_flagged = not show_flagged
    hide_unflagged = not show_unflagged

    # Location-type filter is applied in Python (mirrors filter_by_display) so it
    # respects user-modified locations from user_locs_map, just like get_reports.
    _ALL_LOC = frozenset({'localized', 'pending', 'unlocalized'})
    _loc_set = set(loc_filter) if loc_filter and set(loc_filter) < _ALL_LOC else None

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
    ).order_by(Report.timestamp.desc()).all()

    # Precompute bbox for every unique (osm_id, osm_type) referenced across all rows.
    # This restores containment-suppression for dots after polygon was moved out of locations.
    from sqlalchemy import tuple_
    osm_keys: set[tuple[str, str]] = set()
    for row in rows:
        for loc in (row[9] or []):
            if isinstance(loc, dict) and loc.get("osm_id") and loc.get("osm_type"):
                osm_keys.add((str(loc["osm_id"]), str(loc["osm_type"])))
    bbox_map: dict[tuple[str, str], list[float]] = {}
    if osm_keys:
        poly_rows = (
            session.query(LocationPolygon)
            .filter(tuple_(LocationPolygon.osm_id, LocationPolygon.osm_type).in_(
                _osm_keys_with_alts(osm_keys)
            ))
            .all()
        )
        for pr in poly_rows:
            if isinstance(pr.polygon, dict):
                bb = _polygon_bbox(pr.polygon)
                if bb:
                    bbox_map[(pr.osm_id, pr.osm_type)] = bb

    dots: list[dict] = []
    for (rid, text, author, platform, timestamp, event_types, event_type, relevance, url, locs_raw) in rows:
        if hide_seen and rid in seen_ids:
            continue
        if hide_flagged and (author or "") in flagged_authors:
            continue
        if hide_unflagged and (author or "") not in flagged_authors:
            continue

        effective_locs: list = (user_locs_map[rid] if rid in user_locs_map else locs_raw) or []

        if _loc_set:
            is_localized = any(
                isinstance(loc, dict) and "osm_id" in loc for loc in effective_locs
            )
            has_pending = (not is_localized) and bool(effective_locs)
            is_unlocalized = not is_localized and not has_pending
            if not (
                (is_localized and 'localized' in _loc_set)
                or (has_pending and 'pending' in _loc_set)
                or (is_unlocalized and 'unlocalized' in _loc_set)
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
                    "new": rid in new_ids,
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
