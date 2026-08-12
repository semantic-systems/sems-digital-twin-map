from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import (
    clear_session_cookie,
    create_session,
    destroy_session,
    get_current_username,
    set_session_cookie,
    verify_password,
)
from ..db import User, get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class MeResponse(BaseModel):
    username: str
    is_admin: bool = False


@router.post("/login", response_model=MeResponse)
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> MeResponse:
    """Verify credentials, open a session, set the httpOnly cookie. Returns 401 on
    bad username OR password (same message either way, so it can't be used to probe
    which usernames exist)."""
    user: User | None = (
        db.query(User).filter(User.username == body.username, User.active.is_(True)).first()
    )
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_session(db, user.username)
    set_session_cookie(response, token)
    return MeResponse(username=user.username, is_admin=user.is_admin)


@router.post("/logout")
def logout(
    response: Response,
    sems_session: str | None = Cookie(default=None),
    sems_session_xs: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    # Either cookie may be the one this browser holds (top-level vs embedded);
    # both carry the same token, so destroying it once ends the session for both.
    destroy_session(db, sems_session or sems_session_xs)
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db),
) -> MeResponse:
    """Who am I — used by the frontend on load to decide login-page vs app, and
    whether to show the admin user-management panel. 401 (via the dependency)
    when there's no valid session."""
    user: User | None = db.query(User).filter(User.username == username).first()
    return MeResponse(username=username, is_admin=bool(user and user.is_admin))
