from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_username
from ..db import Report, get_db

_TIME_WINDOWS = {'1h': 1, '6h': 6, '1d': 24, '3d': 72}

def _since_from_window(time_window: str | None) -> datetime | None:
    if not time_window or time_window not in _TIME_WINDOWS:
        return None
    return datetime.now(timezone.utc) - timedelta(hours=_TIME_WINDOWS[time_window])

def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string (accepts trailing 'Z'); None on failure/empty."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def _resolve_time_range(
    time_window: str | None, since: str | None, until: str | None
) -> tuple[datetime | None, datetime | None]:
    """A custom since/until range takes precedence over the preset time_window."""
    custom_since = _parse_iso(since)
    custom_until = _parse_iso(until)
    if custom_since is not None or custom_until is not None:
        return custom_since, custom_until
    return _since_from_window(time_window), None

def _parse_area(area: str | None) -> list | None:
    """Parse the drawn-area query param — a flat 'lat,lon,lat,lon,…' string — into a
    [lat, lon] ring. Returns None on empty/malformed input or a degenerate ring
    (fewer than 3 points), in which case the spatial filter is simply not applied."""
    if not area:
        return None
    try:
        nums = [float(x) for x in area.split(",") if x.strip() != ""]
    except ValueError:
        return None
    if len(nums) < 6 or len(nums) % 2 != 0:  # need ≥3 points (6 numbers), in pairs
        return None
    return [[nums[i], nums[i + 1]] for i in range(0, len(nums), 2)]
from ..schemas.report import (
    DotsResponse,
    FlagRequest,
    HideRequest,
    LocationsRequest,
    NewCountResponse,
    VersionResponse,
    ReportDTO,
    ReportsBundleResponse,
    ReportsResponse,
)
from ..services import report_service as svc

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# GET /  — list reports for a user
# ---------------------------------------------------------------------------

@router.get("/", response_model=ReportsResponse)
def get_reports_endpoint(
    username: str = Depends(get_current_username),
    loc_filter: list[str] = Query(default=[]),
    platforms: list[str] = Query(default=[], alias="platform"),
    event_types: list[str] = Query(default=[], alias="event_type"),
    relevances: list[str] = Query(default=[], alias="relevance"),
    show_hidden: bool = Query(False),
    show_flagged: bool = Query(True),
    show_unflagged: bool = Query(True),
    limit: int = Query(50, ge=1, le=2000),
    search: str | None = Query(None),
    time_window: str | None = Query(None),
    since: str | None = Query(None, description="ISO8601 lower time bound (custom range)"),
    until: str | None = Query(None, description="ISO8601 upper time bound (custom range)"),
    only_new: bool = Query(False),
    only_issues: bool = Query(False, description="Show only reports whose extraction pipeline failed"),
    area: str | None = Query(None, description="Drawn-area filter: flat 'lat,lon,lat,lon,…' ring"),
    session: Session = Depends(get_db),
) -> ReportsResponse:
    from ..config import settings

    eff_since, eff_until = _resolve_time_range(time_window, since, until)
    res = svc.get_reports(
        session=session,
        username=username,
        loc_filter=loc_filter or None,
        platforms=platforms or None,
        event_types=event_types or None,
        relevances=relevances or None,
        show_hidden=show_hidden,
        show_flagged=show_flagged,
        show_unflagged=show_unflagged,
        demo_mode=settings.DEMO_MODE,
        limit=limit,
        search=search or None,
        since=eff_since,
        until=eff_until,
        only_new=only_new,
        only_issues=only_issues,
        spatial_polygon=_parse_area(area),
    )
    return ReportsResponse(
        reports=res.reports,
        pending_count=res.pending_count,
        loaded_at=res.loaded_at,
        event_type_totals=res.event_type_totals,
        relevance_totals=res.relevance_totals,
        location_counts=res.location_counts,
        all_platforms=res.all_platforms,
        platform_counts=res.platform_counts,
        platform_added_counts=res.platform_added_counts,
        has_more=res.has_more,
        total_count=res.total_count,
        unseen_count=res.unseen_count,
        processing_status_totals=res.processing_status_totals,
        reports_total_count=res.reports_total_count,
        reports_unseen_count=res.reports_unseen_count,
    )


# ---------------------------------------------------------------------------
# GET /new-count
# ---------------------------------------------------------------------------

@router.get("/new-count", response_model=NewCountResponse)
def new_count_endpoint(
    username: str = Depends(get_current_username),
    since: str = Query(..., description="ISO8601 datetime string"),
    loc_filter: list[str] = Query(default=[]),
    platforms: list[str] = Query(default=[], alias="platform"),
    event_types: list[str] = Query(default=[], alias="event_type"),
    relevances: list[str] = Query(default=[], alias="relevance"),
    show_hidden: bool = Query(False),
    show_flagged: bool = Query(True),
    show_unflagged: bool = Query(True),
    session: Session = Depends(get_db),
) -> NewCountResponse:
    from ..config import settings

    eff_platform, eff_events, eff_relevance = svc.normalize_filters(
        platforms or None, event_types or None, relevances or None
    )
    count = svc.get_new_count(
        session=session,
        username=username,
        since_iso=since,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        loc_filter=loc_filter or None,
        show_hidden=show_hidden,
        show_flagged=show_flagged,
        show_unflagged=show_unflagged,
        demo_mode=settings.DEMO_MODE,
    )
    return NewCountResponse(count=count)


# ---------------------------------------------------------------------------
# GET /version  — cheap change token (must be before /{report_id})
# ---------------------------------------------------------------------------

@router.get("/version", response_model=VersionResponse)
def version_endpoint(
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> VersionResponse:
    """Poll target: the frontend refetches the full bundle only when this
    token changes — see report_service.get_change_token."""
    return VersionResponse(token=svc.get_change_token(session, username))


# ---------------------------------------------------------------------------
# GET /dots  — map dot positions (must be before /{report_id})
# ---------------------------------------------------------------------------

@router.get("/dots", response_model=DotsResponse)
def dots_endpoint(
    username: str = Depends(get_current_username),
    loc_filter: list[str] = Query(default=[]),
    platforms: list[str] = Query(default=[], alias="platform"),
    event_types: list[str] = Query(default=[], alias="event_type"),
    relevances: list[str] = Query(default=[], alias="relevance"),
    show_hidden: bool = Query(False),
    show_flagged: bool = Query(True),
    show_unflagged: bool = Query(True),
    search: str | None = Query(None),
    time_window: str | None = Query(None),
    since: str | None = Query(None, description="ISO8601 lower time bound (custom range)"),
    until: str | None = Query(None, description="ISO8601 upper time bound (custom range)"),
    only_new: bool = Query(False),
    only_issues: bool = Query(False),
    area: str | None = Query(None, description="Drawn-area filter: flat 'lat,lon,lat,lon,…' ring"),
    session: Session = Depends(get_db),
) -> DotsResponse:
    from ..config import settings

    eff_platform, eff_events, eff_relevance = svc.normalize_filters(
        platforms or None, event_types or None, relevances or None
    )
    eff_since, eff_until = _resolve_time_range(time_window, since, until)
    dots = svc.build_dots(
        session=session,
        username=username,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        loc_filter=loc_filter or None,
        show_hidden=show_hidden,
        show_flagged=show_flagged,
        show_unflagged=show_unflagged,
        demo_mode=settings.DEMO_MODE,
        search=search or None,
        since=eff_since,
        until=eff_until,
        only_new=only_new,
        only_issues=only_issues,
        spatial_polygon=_parse_area(area),
    )
    return DotsResponse(dots=dots)


# ---------------------------------------------------------------------------
# GET /bundle  — reports list + map dots in one round trip (must precede /{id})
# ---------------------------------------------------------------------------

@router.get("/bundle", response_model=ReportsBundleResponse)
def bundle_endpoint(
    username: str = Depends(get_current_username),
    loc_filter: list[str] = Query(default=[]),
    platforms: list[str] = Query(default=[], alias="platform"),
    event_types: list[str] = Query(default=[], alias="event_type"),
    relevances: list[str] = Query(default=[], alias="relevance"),
    show_hidden: bool = Query(False),
    show_flagged: bool = Query(True),
    show_unflagged: bool = Query(True),
    limit: int = Query(50, ge=1, le=2000),
    search: str | None = Query(None),
    time_window: str | None = Query(None),
    since: str | None = Query(None, description="ISO8601 lower time bound (custom range)"),
    until: str | None = Query(None, description="ISO8601 upper time bound (custom range)"),
    only_new: bool = Query(False),
    only_issues: bool = Query(False, description="Show only reports whose extraction pipeline failed"),
    area: str | None = Query(None, description="Drawn-area filter: flat 'lat,lon,lat,lon,…' ring"),
    session: Session = Depends(get_db),
) -> ReportsBundleResponse:
    from ..config import settings

    eff_since, eff_until = _resolve_time_range(time_window, since, until)
    spatial_polygon = _parse_area(area)
    res = svc.get_reports(
        session=session,
        username=username,
        loc_filter=loc_filter or None,
        platforms=platforms or None,
        event_types=event_types or None,
        relevances=relevances or None,
        show_hidden=show_hidden,
        show_flagged=show_flagged,
        show_unflagged=show_unflagged,
        demo_mode=settings.DEMO_MODE,
        limit=limit,
        search=search or None,
        since=eff_since,
        until=eff_until,
        only_new=only_new,
        only_issues=only_issues,
        spatial_polygon=spatial_polygon,
    )
    eff_platform, eff_events, eff_relevance = svc.normalize_filters(
        platforms or None, event_types or None, relevances or None
    )
    dots = svc.build_dots(
        session=session,
        username=username,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        loc_filter=loc_filter or None,
        show_hidden=show_hidden,
        show_flagged=show_flagged,
        show_unflagged=show_unflagged,
        demo_mode=settings.DEMO_MODE,
        search=search or None,
        since=eff_since,
        until=eff_until,
        only_new=only_new,
        only_issues=only_issues,
        spatial_polygon=spatial_polygon,
    )
    return ReportsBundleResponse(
        reports=res.reports,
        pending_count=res.pending_count,
        loaded_at=res.loaded_at,
        event_type_totals=res.event_type_totals,
        relevance_totals=res.relevance_totals,
        location_counts=res.location_counts,
        all_platforms=res.all_platforms,
        platform_counts=res.platform_counts,
        platform_added_counts=res.platform_added_counts,
        has_more=res.has_more,
        total_count=res.total_count,
        unseen_count=res.unseen_count,
        processing_status_totals=res.processing_status_totals,
        reports_total_count=res.reports_total_count,
        reports_unseen_count=res.reports_unseen_count,
        dots=dots,
    )


# ---------------------------------------------------------------------------
# POST /admit-all  — advance the user's admission watermark to "now"
# ---------------------------------------------------------------------------

@router.post("/admit-all")
def admit_all_endpoint(
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Admission is a per-user watermark over ingestion order (see UserAdmission):
    admit-all simply advances it to the current max report id. Filters control
    what the user SEES; the watermark controls the "nothing appears without an
    explicit admit" property.
    """
    admitted = svc.advance_admission(username, session)
    return {"admitted": admitted}


# ---------------------------------------------------------------------------
# GET /tour-example  — the onboarding tour's permanent example report
# (must precede /{report_id} — a literal segment, not an int path param)
# ---------------------------------------------------------------------------

@router.get("/tour-example", response_model=ReportDTO)
def tour_example_endpoint(
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> ReportDTO:
    try:
        return svc.get_tour_example(session=session, username=username)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /{report_id}
# ---------------------------------------------------------------------------

@router.get("/{report_id}", response_model=ReportDTO)
def get_report_endpoint(
    report_id: int,
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> ReportDTO:
    report: Report | None = session.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    user_state = svc.get_user_state(username, session)
    seen_ids = user_state.hidden_ids
    flagged_authors = user_state.flagged_authors
    user_locs_map = user_state.locs_map
    new_ids: set[int] = {report_id} if user_state.is_new(report_id) else set()
    from ..db import UserReportState

    user_state_row = (
        session.query(UserReportState)
        .filter(
            UserReportState.username == username,
            UserReportState.report_id == report_id,
        )
        .first()
    )

    dto = svc.build_report_dto(
        report=report,
        user_state_row=user_state_row,
        user_locs_map=user_locs_map,
        seen_ids=seen_ids,
        flagged_authors=flagged_authors,
        new_ids=new_ids,
    )
    # Re-attach polygon data so the frontend can render area overlays.
    enriched = svc.enrich_with_polygons(session, [loc.model_dump() for loc in dto.locations])
    dto.locations = svc._coerce_locations(enriched)
    return dto


# ---------------------------------------------------------------------------
# PATCH /{report_id}/hide
# ---------------------------------------------------------------------------

@router.patch("/{report_id}/hide")
def hide_endpoint(
    report_id: int,
    body: HideRequest,
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    svc.toggle_hide(
        session=session,
        username=username,
        report_id=report_id,
        hide=body.hide,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# PATCH /{report_id}/flag
# ---------------------------------------------------------------------------

@router.patch("/{report_id}/flag")
def flag_endpoint(
    report_id: int,
    body: FlagRequest,
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    report: Report | None = session.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    author = report.author or ""
    if not author:
        return {"ok": True, "affected": 0}

    affected = svc.toggle_flag(
        session=session,
        username=username,
        author=author,
        flag=body.flag,
    )
    return {"ok": True, "affected": affected}


# ---------------------------------------------------------------------------
# PATCH /{report_id}/acknowledge
# ---------------------------------------------------------------------------

@router.patch("/{report_id}/acknowledge")
def acknowledge_endpoint(
    report_id: int,
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    svc.acknowledge_report(
        session=session,
        username=username,
        report_id=report_id,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# PATCH /{report_id}/locations
# ---------------------------------------------------------------------------

@router.patch("/{report_id}/locations")
def update_locations_endpoint(
    report_id: int,
    body: LocationsRequest,
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    locations_raw = [loc.model_dump(exclude_none=False) for loc in body.locations]
    svc.update_locations(
        session=session,
        username=username,
        report_id=report_id,
        locations=locations_raw,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# DELETE /{report_id}/locations
# ---------------------------------------------------------------------------

@router.delete("/{report_id}/locations")
def restore_locations_endpoint(
    report_id: int,
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    svc.restore_locations(
        session=session,
        username=username,
        report_id=report_id,
    )
    return {"ok": True}
