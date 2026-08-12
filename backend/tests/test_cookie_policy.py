"""
Session-cookie attributes and the Origin check that backs them.

The map runs in two contexts: a normal top-level tab, and embedded as a
cross-site iframe (the RescueMate Lagebild on uni-hamburg.de framing
map.skynet.coypu.org). Neither single cookie policy serves both — SameSite=Lax is
never stored in the frame, and Safari will not send a SameSite=None+Partitioned
cookie back on a plain top-level request — so an embeddable deployment issues
BOTH, and either is accepted on read. The invariants that make that work are easy
to break by editing one of the call sites, hence pinned here.
"""
import pytest
from starlette.responses import Response

from app.auth import (
    SESSION_COOKIE,
    SESSION_COOKIE_EMBEDDED,
    _cookie_kwargs,
    _embedded_cookie_kwargs,
    clear_session_cookie,
    set_session_cookie,
)
from app.config import settings
from app.csrf import is_allowed_origin


@pytest.fixture
def cross_site(monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_SAMESITE", "none")
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)  # must be overridden anyway


@pytest.fixture
def same_site(monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_SAMESITE", "lax")
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)


def _cookie_headers(fn) -> list[str]:
    response = Response()
    fn(response)
    return [v.decode() for k, v in response.raw_headers if k == b"set-cookie"]


def _header_for(headers: list[str], name: str) -> str:
    match = [h for h in headers if h.startswith(f"{name}=")]
    assert len(match) == 1, f"expected exactly one {name} cookie, got {headers}"
    return match[0]


# --- attributes -----------------------------------------------------------

def test_embedded_cookie_forces_secure():
    """Browsers reject SameSite=None without Secure, so it must not depend on the
    COOKIE_SECURE setting."""
    kwargs = _embedded_cookie_kwargs()
    assert kwargs["samesite"] == "none"
    assert kwargs["secure"] is True


def test_first_party_cookie_is_always_lax(cross_site):
    """Even on an embeddable deployment the first-party cookie stays Lax — that is
    the one Safari actually sends back in a top-level tab."""
    kwargs = _cookie_kwargs()
    assert kwargs["samesite"] == "lax"
    assert kwargs["secure"] is False


def test_partitioned_never_goes_through_starlette():
    """Starlette's set_cookie(partitioned=True) raises below Python 3.14 and the
    backend image runs 3.11 — passing it would 500 every login, so the attribute
    must be appended to the raw header instead of handed to set_cookie."""
    assert "partitioned" not in _cookie_kwargs()
    assert "partitioned" not in _embedded_cookie_kwargs()


def test_embeddable_deployment_sets_both_cookies(cross_site):
    headers = _cookie_headers(lambda r: set_session_cookie(r, "tok123"))
    assert len(headers) == 2

    first_party = _header_for(headers, SESSION_COOKIE)
    assert "tok123" in first_party
    assert "SameSite=lax" in first_party
    assert "Partitioned" not in first_party
    assert "HttpOnly" in first_party

    embedded = _header_for(headers, SESSION_COOKIE_EMBEDDED)
    assert "tok123" in embedded          # same token, so either resolves the session
    assert "SameSite=none" in embedded
    assert "Secure" in embedded
    assert "Partitioned" in embedded
    assert "HttpOnly" in embedded


def test_clear_matches_set_attributes(cross_site):
    """A partitioned cookie is a distinct cookie to the browser: logging out with
    different attributes would leave the session cookie in place."""
    set_headers = _cookie_headers(lambda r: set_session_cookie(r, "tok123"))
    clear_headers = _cookie_headers(clear_session_cookie)
    assert len(clear_headers) == len(set_headers) == 2

    def attrs(header: str) -> set[str]:
        return {p.strip() for p in header.split(";")[1:] if not p.strip().startswith(("Max-Age", "expires"))}

    for name in (SESSION_COOKIE, SESSION_COOKIE_EMBEDDED):
        assert attrs(_header_for(set_headers, name)) == attrs(_header_for(clear_headers, name))
        assert "Max-Age=0" in _header_for(clear_headers, name)


def test_non_embeddable_deployment_sets_only_the_first_party_cookie(same_site):
    """Nothing to embed means no reason to hand out a cross-site cookie at all."""
    headers = _cookie_headers(lambda r: set_session_cookie(r, "tok123"))
    assert len(headers) == 1
    assert "Partitioned" not in headers[0]
    assert headers[0].startswith(f"{SESSION_COOKIE}=")


# --- Origin check ---------------------------------------------------------

ALLOWED = {"http://localhost:5173"}


def test_same_origin_allowed():
    assert is_allowed_origin("https://map.skynet.coypu.org", "map.skynet.coypu.org", ALLOWED)


def test_configured_origin_allowed():
    assert is_allowed_origin("http://localhost:5173", "localhost:8052", ALLOWED)


def test_foreign_origin_blocked():
    assert not is_allowed_origin("https://evil.example", "map.skynet.coypu.org", ALLOWED)


def test_missing_origin_allowed():
    """Non-browser clients (curl, scripts) send no Origin and carry no ambient
    cookie — blocking them would break tooling without closing an attack."""
    assert is_allowed_origin(None, "map.skynet.coypu.org", ALLOWED)
    assert is_allowed_origin("", "map.skynet.coypu.org", ALLOWED)


def test_host_mismatch_on_lookalike_origin_blocked():
    """Substring/suffix confusion must not pass — netloc is compared exactly."""
    assert not is_allowed_origin(
        "https://map.skynet.coypu.org.evil.example", "map.skynet.coypu.org", ALLOWED
    )
