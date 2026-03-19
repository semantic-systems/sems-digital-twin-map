from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.report_service import get_user_state

router = APIRouter(prefix="/api/v1/user", tags=["user"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class InitRequest(BaseModel):
    username: str


# ---------------------------------------------------------------------------
# POST /init
# ---------------------------------------------------------------------------

@router.post("/init")
def init_user(body: InitRequest) -> dict[str, Any]:
    """
    Acknowledge a user session.  No DB rows are created here — all
    UserReportState rows are created lazily on first action.
    """
    return {"username": body.username, "ok": True}


# ---------------------------------------------------------------------------
# GET /{username}/state
# ---------------------------------------------------------------------------

@router.get("/{username}/state")
def user_state(
    username: str,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the full aggregated state for a user:
      - admitted_ids: list[int]   — reports admitted to the sidebar
      - flagged_authors: list[str]
      - hide_ids: list[int]       — reports marked as seen/hidden
      - new_ids: list[int]        — admitted but not yet acknowledged
      - location_overrides: dict  — {str(report_id): list[LocationEntry]}
    """
    seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, _ = get_user_state(
        username, session
    )

    return {
        "admitted_ids": sorted(added_ids),
        "flagged_authors": sorted(flagged_authors),
        "hide_ids": sorted(seen_ids),
        "new_ids": sorted(new_ids),
        "location_overrides": {
            str(rid): locs for rid, locs in user_locs_map.items()
        },
    }
