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
      - admitted_up_to_id: int    — admission watermark; report ids <= this are
                                    admitted to the sidebar (see UserAdmission)
      - flagged_authors: list[str]
      - hide_ids: list[int]       — reports marked as seen/hidden
      - acknowledged_ids: list[int] — reports the user has explicitly opened
      - location_overrides: dict  — {str(report_id): list[LocationEntry]}
    """
    state = get_user_state(username, session)

    return {
        "admitted_up_to_id": state.admitted_up_to,
        "flagged_authors": sorted(state.flagged_authors),
        "hide_ids": sorted(state.hidden_ids),
        "acknowledged_ids": sorted(state.acknowledged_ids),
        "location_overrides": {
            str(rid): locs for rid, locs in state.locs_map.items()
        },
    }
