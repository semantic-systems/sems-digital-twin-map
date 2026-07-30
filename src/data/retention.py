"""
Retention policy for reports.

Reports are a rolling live picture of the last few days, not an archive: the UI's
widest preset window looks back 3 days (see _TIME_WINDOWS in
backend/app/routers/reports.py) while ingestion runs forever, so without a
retention window the reports table just grows without bound. Anything older than
REPORT_RETENTION_DAYS (7 by default) is therefore deleted from the database.

Lives in the shared `data` package rather than under backend/ so the ingestion
process (src/server_reports.py) or an ad-hoc script can enforce the same policy
with the same code; the backend is what actually runs it periodically today (see
backend/app/main.py::_purge_loop).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from .model import Report, UserReportState

DEFAULT_RETENTION_DAYS = 7

# The onboarding tour's example report is seeded exactly once, at backend startup
# (main.py::_init_db), and carries a real timestamp — so the age check alone would
# delete it a week after the first start and permanently 404
# GET /api/v1/reports/tour-example until the next restart. Same prefix match the
# normal listings use to hide it (report_service.build_report_query).
TOUR_EXAMPLE_PREFIX = "tour-example"


def retention_days() -> int:
    """The retention window in days, from REPORT_RETENTION_DAYS.

    Falls back to DEFAULT_RETENTION_DAYS when unset or unparsable — a typo in the
    environment must not silently turn into "delete everything". 0 or negative
    disables purging altogether.
    """
    raw = os.getenv("REPORT_RETENTION_DAYS", "").strip()
    if not raw:
        return DEFAULT_RETENTION_DAYS
    try:
        return int(raw)
    except ValueError:
        print(f"[retention] ignoring unparsable REPORT_RETENTION_DAYS={raw!r}", flush=True)
        return DEFAULT_RETENTION_DAYS


def purge_cutoff(days: int, now: datetime | None = None) -> datetime:
    """Naive-UTC timestamp before which reports are considered expired.

    Naive because reports.timestamp is a plain TIMESTAMP holding UTC (see
    report_service._now_utc) — comparing it against an aware datetime raises in
    psycopg.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    return now - timedelta(days=days)


def expired_criteria(cutoff: datetime) -> list[ColumnElement[bool]]:
    """WHERE criteria selecting the reports the purge is allowed to delete."""
    return [
        Report.timestamp < cutoff,
        Report.identifier.notlike(f"{TOUR_EXAMPLE_PREFIX}%"),
    ]


def purge_old_reports(session: Session, days: int | None = None) -> int:
    """Delete every report older than the retention window; returns the row count.

    Idempotent and cheap enough to call on a timer — the age filter uses the
    ix_reports_timestamp index. Orphaned location_polygons rows are deliberately
    left alone: that table is a deduplicated cache shared across reports and
    refilling it means re-fetching WKT geometries from the SPARQL endpoint.
    """
    days = retention_days() if days is None else days
    if days <= 0:
        return 0

    criteria = expired_criteria(purge_cutoff(days))

    # Child rows explicitly first: user_report_state.report_id is declared
    # ON DELETE CASCADE, but a database created before that clause existed won't
    # have it, and a bulk DELETE bypasses the ORM-level cascade in either case.
    # The id list stays a subquery so this is one round trip, not a fetch-then-send.
    session.execute(
        delete(UserReportState).where(
            UserReportState.report_id.in_(select(Report.id).where(*criteria))
        )
    )
    result = session.execute(delete(Report).where(*criteria))
    session.commit()
    return result.rowcount or 0
