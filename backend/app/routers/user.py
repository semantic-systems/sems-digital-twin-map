from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_username
from ..db import get_db
from ..services.report_service import get_user_state

router = APIRouter(prefix="/api/v1/user", tags=["user"])


# ---------------------------------------------------------------------------
# GET /state  — the current (authenticated) user's aggregated state
# ---------------------------------------------------------------------------

@router.get("/state")
def user_state(
    username: str = Depends(get_current_username),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the full aggregated state for the CURRENT user (derived from the
    session — a user can only read their own state):
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
