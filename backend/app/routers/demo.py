from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import Report, UserReportState, get_session, get_db

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# Walk up the directory tree to find src/data/demo_data.json (works both locally and in Docker)
_search = os.path.abspath(os.path.dirname(__file__))
_DEMO_JSON: str = ""
for _ in range(6):
    _candidate = os.path.join(_search, "src", "data", "demo_data.json")
    if os.path.exists(_candidate):
        _DEMO_JSON = _candidate
        break
    _parent = os.path.dirname(_search)
    if _parent == _search:
        break
    _search = _parent

# ---------------------------------------------------------------------------
# Trickle state (module-level — one task per server process)
# ---------------------------------------------------------------------------
_trickle_task: asyncio.Task | None = None
_trickle_total: int = 0
_trickle_done: int = 0
_trickle_running: bool = False

TRICKLE_INTERVAL_SECONDS: float = 10.0  # one new report per polling cycle


async def _trickle_worker(records: list[dict]) -> None:
    global _trickle_done, _trickle_running
    _trickle_running = True
    _trickle_done = 0

    for rd in records:
        await asyncio.sleep(TRICKLE_INTERVAL_SECONDS)
        try:
            with get_session() as session:
                session.add(
                    Report(
                        identifier=rd["identifier"],
                        text=rd["text"],
                        url=rd["url"],
                        platform=rd["platform"],
                        timestamp=datetime.utcnow(),
                        event_type=rd["event_type"],
                        relevance=rd["relevance"],
                        locations=rd.get("locations", []),
                        original_locations=rd.get("locations", []),
                        author=rd.get("author", ""),
                        seen=False,
                        author_flagged=False,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            print(f"[demo trickle] error inserting report: {exc}")

        _trickle_done += 1

    _trickle_running = False


def _cancel_trickle() -> None:
    global _trickle_task
    if _trickle_task and not _trickle_task.done():
        _trickle_task.cancel()
    _trickle_task = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status")
def demo_status() -> dict[str, Any]:
    """Returns demo mode flag and current trickle progress."""
    return {
        "demo_mode": settings.DEMO_MODE,
        "running": _trickle_running,
        "done": _trickle_done,
        "total": _trickle_total,
    }


@router.post("/reset")
async def demo_reset(session: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Clears all reports and user state, then trickles demo reports in one-by-one
    at the polling interval (10 s each).  Only available when DEMO_MODE=True.
    """
    global _trickle_task, _trickle_total, _trickle_done, _trickle_running

    if not settings.DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not found")

    if not os.path.exists(_DEMO_JSON):
        raise HTTPException(
            status_code=500,
            detail=(
                f"Demo data file not found: {_DEMO_JSON}. "
                "Run `python src/prepare_demo.py` first."
            ),
        )

    with open(_DEMO_JSON, "r", encoding="utf-8") as fh:
        records: list[dict] = json.load(fh)

    # Cancel any in-progress trickle
    _cancel_trickle()

    # Wipe all data
    session.query(UserReportState).delete()
    session.query(Report).delete()
    session.commit()

    # Reset counters
    _trickle_total = len(records)
    _trickle_done = 0
    _trickle_running = False

    # Start background trickle
    _trickle_task = asyncio.create_task(_trickle_worker(records))

    return {"ok": True, "total": _trickle_total, "interval_seconds": TRICKLE_INTERVAL_SECONDS}
