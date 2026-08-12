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
# Cross-site-capable twin of the above, only issued when the deployment is
# configured as embeddable. Separate name so the two can carry different
# SameSite/Partitioned attributes without overwriting each other — see
# set_session_cookie for why one cookie cannot serve both contexts.
SESSION_COOKIE_EMBEDDED = "sems_session_xs"
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


def _is_cross_site() -> bool:
    """Whether the app is configured to be embedded in a page on another site."""
    from .config import settings

    return settings.COOKIE_SAMESITE == "none"


def _cookie_kwargs() -> dict:
    """Attributes for the first-party cookie — the one a normal, top-level visit
    uses. Always SameSite=Lax and never Partitioned, whatever COOKIE_SAMESITE says;
    the embedded case is served by its own cookie (see _embedded_cookie_kwargs)
    rather than by weakening this one.

    Safari is why the two are split. A cookie carrying SameSite=None+Partitioned is
    not sent back on a plain top-level request there, so serving both contexts from
    one cookie meant Safari users could log in (200 + Set-Cookie) and then have
    every following request come back 401 — while Chrome and Firefox were fine.
    """
    from .config import settings

    return {
        "path": "/",
        "samesite": "lax",
        "secure": settings.COOKIE_SECURE,
    }


def _embedded_cookie_kwargs() -> dict:
    """Attributes for the cookie used when the app runs inside a cross-site iframe.

    SameSite=None is the only value a browser will send from a third-party frame,
    and it is only accepted together with Secure — so Secure is forced here rather
    than left to COOKIE_SECURE, which would otherwise hand the browser a cookie it
    silently drops with no error anyone could act on.
    """
    return {
        "path": "/",
        "samesite": "none",
        "secure": True,
    }


def _mark_partitioned(response: Response, cookie_name: str) -> None:
    """Append `Partitioned` (CHIPS) to the named cookie just written.

    Chrome requires it for a cookie used inside a third-party frame. Done by hand
    on the raw header because Starlette's set_cookie(partitioned=True) raises
    below Python 3.14 — stdlib http.cookies only learned the attribute there — and
    the backend image runs 3.11, so using the parameter would turn every login
    into a 500.
    """
    prefix = cookie_name.encode() + b"="
    for i, (name, value) in enumerate(response.raw_headers):
        if name == b"set-cookie" and value.startswith(prefix):
            if b"Partitioned" not in value:
                response.raw_headers[i] = (name, value + b"; Partitioned")
            return


def set_session_cookie(response: Response, token: str) -> None:
    """Write the session token as a first-party cookie, plus — when the deployment
    is also embedded somewhere — a second, cross-site-capable copy.

    Two cookies rather than one compromise policy: a page inside a cross-site
    iframe fetches its OWN origin, so `Sec-Fetch-Site` reads `same-origin` in both
    the framed and the top-level case and the server cannot tell them apart from
    the request. Offering both lets each browser send whichever one it is willing
    to store; they carry the same token, so either resolves the same session.
    """
    max_age = SESSION_DAYS * 24 * 3600
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        **_cookie_kwargs(),
    )
    if _is_cross_site():
        response.set_cookie(
            key=SESSION_COOKIE_EMBEDDED,
            value=token,
            max_age=max_age,
            httponly=True,
            **_embedded_cookie_kwargs(),
        )
        _mark_partitioned(response, SESSION_COOKIE_EMBEDDED)


def clear_session_cookie(response: Response) -> None:
    # Not response.delete_cookie(): it takes no `partitioned` argument, and the
    # expiry it writes has to carry the exact same attributes as the cookie it is
    # meant to remove. An expired set_cookie is what delete_cookie does internally.
    response.set_cookie(
        key=SESSION_COOKIE,
        value="",
        max_age=0,
        expires=0,
        httponly=True,
        **_cookie_kwargs(),
    )
    if _is_cross_site():
        response.set_cookie(
            key=SESSION_COOKIE_EMBEDDED,
            value="",
            max_age=0,
            expires=0,
            httponly=True,
            **_embedded_cookie_kwargs(),
        )
        _mark_partitioned(response, SESSION_COOKIE_EMBEDDED)


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
    sems_session_xs: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> str:
    """The authenticated user's username, derived from the session cookie.
    Raises 401 when not logged in — this is what every user-scoped endpoint uses
    instead of accepting a client-supplied username.

    Either cookie is accepted: which of the two the browser sends depends on
    whether the app is running top-level or inside a cross-site frame, and both
    carry the same token."""
    username = resolve_session_user(db, sems_session or sems_session_xs)
    if username is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username


def ensure_default_admin(session: Session) -> None:
    """Create the bootstrap admin from DEFAULT_ADMIN_USER/PASSWORD if set and that
    username doesn't exist yet. Idempotent and non-destructive — it never resets an
    existing account's password, so an admin who changes their password in-app
    keeps it across restarts. Called once at startup."""
    from .config import settings

    user = settings.DEFAULT_ADMIN_USER.strip()
    password = settings.DEFAULT_ADMIN_PASSWORD
    if not user or not password:
        return
    if session.query(User).filter(User.username == user).first() is not None:
        return
    session.add(User(username=user, password_hash=hash_password(password), active=True, is_admin=True))
    session.commit()
    warn = "  ⚠ CHANGE THIS PASSWORD after first login." if len(password) < 12 else ""
    print(f"[startup] Created bootstrap admin '{user}'.{warn}", flush=True)


def get_current_admin(
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db),
) -> str:
    """Like get_current_username but also requires the account to be an admin —
    401 if not logged in, 403 if logged in without the admin role. Gates the
    user-management endpoints."""
    user: User | None = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return username
