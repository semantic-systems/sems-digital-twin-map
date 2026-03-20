from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import Report, get_db
from ..schemas.report import (
    AcknowledgeRequest,
    AdmitRequest,
    AdmitResponse,
    FlagRequest,
    HideRequest,
    LocationsRequest,
    NewCountResponse,
    ReportDTO,
    ReportsResponse,
)
from pydantic import BaseModel

class _AdmitAllRequest(BaseModel):
    username: str
from ..services import report_service as svc

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# GET /  — list reports for a user
# ---------------------------------------------------------------------------

@router.get("/", response_model=ReportsResponse)
def get_reports_endpoint(
    username: str = Query(..., description="The requesting user's name"),
    loc_filter: str = Query("all", description="'all'|'localized'|'pending'|'unlocalized'"),
    platforms: list[str] = Query(default=[], alias="platform"),
    event_types: list[str] = Query(default=[], alias="event_type"),
    relevances: list[str] = Query(default=[], alias="relevance"),
    show_hidden: bool = Query(False),
    show_flagged: bool = Query(True),
    show_unflagged: bool = Query(True),
    limit: int = Query(25, ge=1, le=500),
    session: Session = Depends(get_db),
) -> ReportsResponse:
    from ..config import settings

    reports, pending_count, loaded_at, event_type_totals, all_platforms, platform_counts = svc.get_reports(
        session=session,
        username=username,
        loc_filter=loc_filter,
        platforms=platforms or None,
        event_types=event_types or None,
        relevances=relevances or None,
        show_hidden=show_hidden,
        show_flagged=show_flagged,
        show_unflagged=show_unflagged,
        demo_mode=settings.DEMO_MODE,
        limit=limit,
    )
    return ReportsResponse(
        reports=reports,
        pending_count=pending_count,
        loaded_at=loaded_at,
        event_type_totals=event_type_totals,
        all_platforms=all_platforms,
        platform_counts=platform_counts,
    )


# ---------------------------------------------------------------------------
# GET /new-count
# ---------------------------------------------------------------------------

@router.get("/new-count", response_model=NewCountResponse)
def new_count_endpoint(
    username: str = Query(...),
    since: str = Query(..., description="ISO8601 datetime string"),
    loc_filter: str = Query("all"),
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
        loc_filter=loc_filter,
        show_hidden=show_hidden,
        show_flagged=show_flagged,
        show_unflagged=show_unflagged,
        demo_mode=settings.DEMO_MODE,
    )
    return NewCountResponse(count=count)


# ---------------------------------------------------------------------------
# GET /dots  — map dot positions (must be before /{report_id})
# ---------------------------------------------------------------------------

@router.get("/dots")
def dots_endpoint(
    username: str = Query(...),
    loc_filter: str = Query("all"),
    platforms: list[str] = Query(default=[], alias="platform"),
    event_types: list[str] = Query(default=[], alias="event_type"),
    relevances: list[str] = Query(default=[], alias="relevance"),
    show_hidden: bool = Query(False),
    show_flagged: bool = Query(True),
    show_unflagged: bool = Query(True),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    from ..config import settings

    eff_platform, eff_events, eff_relevance = svc.normalize_filters(
        platforms or None, event_types or None, relevances or None
    )
    dots = svc.build_dots(
        session=session,
        username=username,
        eff_platform=eff_platform,
        eff_events=eff_events,
        eff_relevance=eff_relevance,
        loc_filter=loc_filter,
        show_hidden=show_hidden,
        show_flagged=show_flagged,
        show_unflagged=show_unflagged,
        demo_mode=settings.DEMO_MODE,
    )
    return {"dots": dots}


# ---------------------------------------------------------------------------
# POST /admit
# ---------------------------------------------------------------------------

@router.post("/admit", response_model=AdmitResponse)
def admit_endpoint(
    body: AdmitRequest,
    session: Session = Depends(get_db),
) -> AdmitResponse:
    admitted = svc.bulk_admit_reports(
        username=body.username,
        report_ids=body.report_ids,
        session=session,
    )
    return AdmitResponse(admitted=admitted)


# ---------------------------------------------------------------------------
# POST /admit-all  — admit every unadmitted report for a user
# ---------------------------------------------------------------------------

@router.post("/admit-all")
def admit_all_endpoint(
    body: _AdmitAllRequest,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    from ..config import settings
    from ..db import Report

    _, _, _, added_ids, _, _ = svc.get_user_state(body.username, session)
    q = session.query(Report.id)
    if settings.DEMO_MODE:
        q = q.filter(Report.identifier.like("demo-%"))
    all_ids: list[int] = [row[0] for row in q.all()]
    pending_ids = [rid for rid in all_ids if rid not in added_ids]
    admitted = svc.bulk_admit_reports(body.username, pending_ids, session)
    return {"admitted": len(admitted)}


# ---------------------------------------------------------------------------
# GET /{report_id}
# ---------------------------------------------------------------------------

@router.get("/{report_id}", response_model=ReportDTO)
def get_report_endpoint(
    report_id: int,
    username: str | None = Query(None),
    session: Session = Depends(get_db),
) -> ReportDTO:
    report: Report | None = session.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    user_locs_map: dict[int, list] = {}
    seen_ids: set[int] = set()
    flagged_authors: set[str] = set()
    new_ids: set[int] = set()
    user_state_row = None

    if username:
        seen_ids, flagged_authors, user_locs_map, _, new_ids, _ = svc.get_user_state(
            username, session
        )
        from ..db import UserReportState

        user_state_row = (
            session.query(UserReportState)
            .filter(
                UserReportState.username == username,
                UserReportState.report_id == report_id,
            )
            .first()
        )

    return svc.build_report_dto(
        report=report,
        user_state_row=user_state_row,
        user_locs_map=user_locs_map,
        seen_ids=seen_ids,
        flagged_authors=flagged_authors,
        new_ids=new_ids,
    )


# ---------------------------------------------------------------------------
# PATCH /{report_id}/hide
# ---------------------------------------------------------------------------

@router.patch("/{report_id}/hide")
def hide_endpoint(
    report_id: int,
    body: HideRequest,
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    svc.toggle_hide(
        session=session,
        username=body.username,
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
        username=body.username,
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
    body: AcknowledgeRequest,
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    svc.acknowledge_report(
        session=session,
        username=body.username,
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
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    locations_raw = [loc.model_dump(exclude_none=False) for loc in body.locations]
    svc.update_locations(
        session=session,
        username=body.username,
        report_id=report_id,
        locations=locations_raw,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# DELETE /{report_id}/locations  (body carries username)
# ---------------------------------------------------------------------------

class _RestoreBody(AcknowledgeRequest):
    pass


@router.delete("/{report_id}/locations")
def restore_locations_endpoint(
    report_id: int,
    body: _RestoreBody,
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    svc.restore_locations(
        session=session,
        username=body.username,
        report_id=report_id,
    )
    return {"ok": True}
