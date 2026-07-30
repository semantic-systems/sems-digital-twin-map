"""
Origin check for state-changing requests.

The session cookie is the only credential, so any page that can make the browser
send it can act as the logged-in user. `SameSite=Lax` used to provide that
protection for free; embedding the app as a cross-site iframe requires
`SameSite=None` (see auth._cookie_kwargs), which gives it up. This middleware
replaces it: an unsafe request whose `Origin` is neither the app's own host nor
explicitly allowed is rejected before it reaches a route.

Deliberately an Origin check and not a CSRF token: the app has no server-rendered
forms, every mutation goes through fetch() from its own JS bundle, and `Origin`
is set by the browser and unspoofable from page JS — a token would add a
handshake and a failure mode without buying anything here.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

# GET/HEAD/OPTIONS must stay reachable cross-site: the frontend bundle itself is
# fetched that way, and CORS preflights are OPTIONS.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def is_allowed_origin(origin: str | None, host: str | None, allowed: set[str]) -> bool:
    """Whether a request carrying this Origin may perform a state-changing call.

    A missing Origin passes: browsers set it on every cross-site request that
    could carry a cookie, so absence means a non-browser client (curl, a script,
    server-to-server) — which has no ambient cookie to abuse in the first place.
    Rejecting it would only break tooling.
    """
    if not origin:
        return True
    if origin in allowed:
        return True
    # Same-origin: the Origin's host matches the Host the request arrived on.
    # Compared without the scheme because docker/nginx.conf forwards Host but not
    # X-Forwarded-Proto, so the app cannot reconstruct its own scheme reliably.
    return host is not None and urlsplit(origin).netloc == host


async def origin_check_middleware(request: Request, call_next):
    """Reject unsafe cross-site requests with 403 before they hit a route."""
    if request.method in SAFE_METHODS:
        return await call_next(request)

    from .config import settings

    allowed = set(settings.CORS_ORIGINS) | set(settings.TRUSTED_ORIGINS)
    if not is_allowed_origin(
        request.headers.get("origin"), request.headers.get("host"), allowed
    ):
        return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked"})

    return await call_next(request)
