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

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..db import Report, UserReportState
from ..schemas.report import LocationEntry, ReportDTO, UserStateDTO

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    added_ids: set[int] | None = None,
    eff_platform: list[str] | None = None,
    eff_events: list[str] | None = None,
    eff_relevance: list[str] | None = None,
    demo_mode: bool = False,
    search: str | None = None,
):
    """
    Returns a SQLAlchemy Query[Report] with all filters applied.
    Does NOT call .all() — callers may add further ordering / limits.
    """
    q = session.query(Report).filter(Report.timestamp <= _now_utc())

    if since is not None:
        q = q.filter(Report.timestamp > since)

    if demo_mode:
        q = q.filter(Report.identifier.like("demo-%"))

    if eff_platform:
        q = q.filter(
            or_(*[Report.platform.like(f"{p}%") for p in eff_platform])
        )

    if eff_events:
        q = q.filter(Report.event_type.in_(eff_events))

    if eff_relevance:
        q = q.filter(Report.relevance.in_(eff_relevance))

    if added_ids is not None:
        q = q.filter(Report.id.in_(added_ids))

    if search:
        term = f"%{search}%"
        q = q.filter(
            or_(Report.text.ilike(term), Report.author.ilike(term))
        )

    return q


# ---------------------------------------------------------------------------
# filter_by_display
# ---------------------------------------------------------------------------

def filter_by_display(
    reports: list[Report],
    loc_filter: str,
    seen_ids: set[int],
    flagged_authors: set[str],
    user_locs_map: dict[int, list],
    hide_seen: bool,
    hide_flagged: bool,
    hide_unflagged: bool,
) -> list[Report]:
    """
    Python-level post-query filtering.
    loc_filter: 'all' | 'localized' | 'pending' | 'unlocalized'
    """
    result: list[Report] = []

    for r in reports:
        if hide_seen and r.id in seen_ids:
            continue
        if hide_flagged and (r.author or "") in flagged_authors:
            continue
        if hide_unflagged and (r.author or "") not in flagged_authors:
            continue

        effective_locs: list = user_locs_map.get(r.id) or r.locations or []
        is_localized = any(
            isinstance(loc, dict) and "osm_id" in loc for loc in effective_locs
        )
        has_pending = (not is_localized) and bool(effective_locs)

        if loc_filter == "localized" and not is_localized:
            continue
        if loc_filter == "pending" and not has_pending:
            continue
        if loc_filter == "unlocalized" and (is_localized or has_pending):
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

    effective_locs_raw = user_locs_map.get(report.id) or report.locations or []
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
        timestamp=report.timestamp,
        event_type=report.event_type,
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
    loc_filter: str = "all",
    platforms: list[str] | None = None,
    event_types: list[str] | None = None,
    relevances: list[str] | None = None,
    show_hidden: bool = False,
    show_flagged: bool = True,
    show_unflagged: bool = True,
    demo_mode: bool = False,
    limit: int = 50,
    search: str | None = None,
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

    # Base query for all reports in DB (admitted + pending), ignoring event_type
    # and platform filters — used for chip totals and platform list.
    all_base_q = build_report_query(
        session,
        eff_platform=None,
        eff_events=None,
        eff_relevance=eff_relevance,
        demo_mode=demo_mode,
    )
    all_base_rows = all_base_q.with_entities(Report.event_type, Report.platform, Report.relevance).all()

    event_type_totals: dict[str, int] = {}
    platform_counts: dict[str, int] = {p: 0 for p in ALL_PLATFORMS}
    relevance_totals: dict[str, int] = {}
    for (et, plat, rel) in all_base_rows:
        event_type_totals[et] = event_type_totals.get(et, 0) + 1
        if plat:
            platform_counts[plat] = platform_counts.get(plat, 0) + 1
        if rel:
            relevance_totals[rel] = relevance_totals.get(rel, 0) + 1
    # Always expose the full known platform list, plus any unexpected ones from DB.
    all_platforms = sorted(platform_counts.keys())

    # Count admitted posts per platform (ignoring event_type / platform filters).
    platform_added_counts: dict[str, int] = {p: 0 for p in ALL_PLATFORMS}
    if added_ids:
        added_rows = (
            build_report_query(
                session,
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
            eff_platform=eff_platform,
            eff_events=eff_events,
            eff_relevance=eff_relevance,
            demo_mode=demo_mode,
        )
        pending_count = pending_q.count()
        loaded_at = datetime.now(timezone.utc).isoformat()
        return [], pending_count, loaded_at, event_type_totals, all_platforms, platform_counts, platform_added_counts, relevance_totals, False

    # Build the main query (only admitted reports)
    q = build_report_query(
        session,
        added_ids=added_ids,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        demo_mode=demo_mode,
        search=search,
    )
    # Overfetch to account for Python-level filtering (show_hidden, loc_filter, etc.)
    sql_limit = limit + 100
    reports_orm: list[Report] = (
        q.order_by(Report.timestamp.desc()).limit(sql_limit).all()
    )

    # Python-level display filtering
    hide_seen = not show_hidden
    hide_flagged = not show_flagged
    hide_unflagged = not show_unflagged

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

    # Determine if there are more results beyond the requested limit
    has_more = len(filtered) > limit
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

    # Pending count = reports that match filters but are NOT yet admitted
    all_matching_ids: set[int] = {
        row[0]
        for row in build_report_query(
            session,
            eff_platform=eff_platform,
            eff_events=eff_events,
            eff_relevance=eff_relevance,
            demo_mode=demo_mode,
        )
        .with_entities(Report.id)
        .all()
    }
    pending_count = len(all_matching_ids - added_ids)

    loaded_at = datetime.now(timezone.utc).isoformat()
    return dtos, pending_count, loaded_at, event_type_totals, all_platforms, platform_counts, platform_added_counts, relevance_totals, has_more


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
    loc_filter: str,
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
    loc_filter: str,
    show_hidden: bool,
    show_flagged: bool,
    show_unflagged: bool,
    demo_mode: bool,
    added_ids: set[int] | None = None,
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
        added_ids=effective_added,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        demo_mode=demo_mode,
    )
    reports_orm: list[Report] = q.all()

    hide_seen = not show_hidden
    hide_flagged = not show_flagged
    hide_unflagged = not show_unflagged

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

    dots: list[dict] = []
    for r in filtered:
        effective_locs: list = user_locs_map.get(r.id) or r.locations or []
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

            dots.append(
                {
                    "report_id": r.id,
                    "lat": lat_f,
                    "lon": lon_f,
                    "seen": r.id in seen_ids,
                    "new": r.id in new_ids,
                    "location_name": loc.get("name") or loc.get("display_name") or "",
                    "text": r.text[:300],
                    "author": r.author or "",
                    "platform": r.platform,
                    "timestamp": r.timestamp.strftime("%H:%M %d.%m.%Y"),
                    "event_type": r.event_type,
                    "relevance": r.relevance,
                    "url": r.url,
                }
            )

    return dots
