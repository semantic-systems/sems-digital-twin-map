"""
Authentication: password hashing, server-side login sessions, and the
`get_current_username` FastAPI dependency that replaces the old trust-the-
`username`-query-param model.

Accounts are admin-provisioned (scripts/create_user.py) — there is no signup.
Passwords are stored as PBKDF2-HMAC-SHA256 hashes (stdlib, no extra dependency;
Django's `pbkdf2_sha256$iterations$salt$hash` format). Login issues a random
opaque token stored in `auth_sessions` and set as an httpOnly cookie; every
request resolves the current user by looking the token up, so sessions are
revocable (logout / deactivation take effect immediately) — unlike a JWT.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .db import User, UserSession, get_db

# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------

_PBKDF2_ITERATIONS = 600_000  # OWASP-recommended floor for PBKDF2-SHA256
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_ALGO}${_PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
        if algo != _ALGO:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)  # constant-time


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

SESSION_COOKIE = "sems_session"
SESSION_DAYS = 30


def _now() -> datetime:
    # naive UTC, matching the rest of the schema (see report_service._now_utc)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_session(session: Session, username: str) -> str:
    """Issue a new session token for `username` and persist it."""
    token = secrets.token_urlsafe(32)
    now = _now()
    session.add(UserSession(
        token=token,
        username=username,
        created_at=now,
        expires_at=now + timedelta(days=SESSION_DAYS),
    ))
    session.commit()
    return token


def destroy_session(session: Session, token: str | None) -> None:
    if not token:
        return
    session.query(UserSession).filter(UserSession.token == token).delete()
    session.commit()


def set_session_cookie(response: Response, token: str) -> None:
    from .config import settings
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


def resolve_session_user(session: Session, token: str | None) -> str | None:
    """Return the username for a valid, unexpired session whose account is still
    active — or None. Expired sessions are cleaned up opportunistically."""
    if not token:
        return None
    row: UserSession | None = session.get(UserSession, token)
    if row is None:
        return None
    if row.expires_at <= _now():
        session.delete(row)
        session.commit()
        return None
    user: User | None = (
        session.query(User).filter(User.username == row.username, User.active.is_(True)).first()
    )
    return user.username if user is not None else None


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_current_username(
    sems_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> str:
    """The authenticated user's username, derived from the session cookie.
    Raises 401 when not logged in — this is what every user-scoped endpoint uses
    instead of accepting a client-supplied username."""
    username = resolve_session_user(db, sems_session)
    if username is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username
