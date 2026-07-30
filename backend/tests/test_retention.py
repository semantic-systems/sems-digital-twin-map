"""
Report retention (data/retention.py). No database: the cutoff maths, the env
parsing and the emitted SQL are all checkable without one, and those are exactly
the parts where a mistake silently deletes the wrong rows.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.dialects import postgresql

import app.db  # noqa: F401  — puts src/ on sys.path so `data.*` imports resolve
from data.model import Report
from data.retention import (
    DEFAULT_RETENTION_DAYS,
    expired_criteria,
    purge_cutoff,
    purge_old_reports,
    retention_days,
)


# --- retention_days -------------------------------------------------------

def test_retention_days_defaults_to_seven(monkeypatch):
    monkeypatch.delenv("REPORT_RETENTION_DAYS", raising=False)
    assert retention_days() == DEFAULT_RETENTION_DAYS == 7


def test_retention_days_reads_env(monkeypatch):
    monkeypatch.setenv("REPORT_RETENTION_DAYS", "3")
    assert retention_days() == 3


def test_retention_days_falls_back_on_garbage(monkeypatch):
    """A typo must not become "delete everything" (cutoff = now)."""
    monkeypatch.setenv("REPORT_RETENTION_DAYS", "seven")
    assert retention_days() == DEFAULT_RETENTION_DAYS
    monkeypatch.setenv("REPORT_RETENTION_DAYS", "  ")
    assert retention_days() == DEFAULT_RETENTION_DAYS


def test_retention_days_zero_is_kept(monkeypatch):
    monkeypatch.setenv("REPORT_RETENTION_DAYS", "0")
    assert retention_days() == 0


# --- purge_cutoff ---------------------------------------------------------

def test_purge_cutoff_is_naive_utc():
    """reports.timestamp is a naive TIMESTAMP holding UTC — an aware cutoff would
    raise in psycopg on comparison."""
    aware = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    cutoff = purge_cutoff(7, now=aware)
    assert cutoff.tzinfo is None
    assert cutoff == datetime(2026, 7, 23, 12, 0)


def test_purge_cutoff_converts_non_utc_offset():
    berlin_noon = datetime(2026, 7, 30, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    assert purge_cutoff(7, now=berlin_noon) == datetime(2026, 7, 23, 10, 0)


def test_purge_cutoff_accepts_naive_now():
    assert purge_cutoff(1, now=datetime(2026, 7, 30, 12, 0)) == datetime(2026, 7, 29, 12, 0)


# --- criteria / emitted SQL ----------------------------------------------

def _compiled(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_criteria_filter_on_age_and_spare_the_tour_example():
    sql = _compiled(delete(Report).where(*expired_criteria(purge_cutoff(7))))
    assert "reports.timestamp <" in sql
    assert "reports.identifier NOT LIKE" in sql


# --- purge_old_reports ----------------------------------------------------

class _RecordingSession:
    """Minimal Session stand-in: records statements, reports 2 deleted rows."""

    def __init__(self):
        self.statements = []
        self.commits = 0

    def execute(self, stmt):
        self.statements.append(_compiled(stmt))
        return type("Result", (), {"rowcount": 2})()

    def commit(self):
        self.commits += 1


def test_purge_deletes_child_state_before_reports():
    session = _RecordingSession()
    assert purge_old_reports(session, days=7) == 2
    assert len(session.statements) == 2
    assert session.statements[0].startswith("DELETE FROM user_report_state")
    assert "FROM reports" in session.statements[0]  # scoped by the same id subquery
    assert session.statements[1].startswith("DELETE FROM reports")
    assert session.commits == 1


def test_purge_disabled_by_zero_or_negative_days():
    """Escape hatch: no cutoff is computed and the session is never touched."""
    for days in (0, -1):
        session = _RecordingSession()
        assert purge_old_reports(session, days=days) == 0
        assert session.statements == []
        assert session.commits == 0
