"""
Session-cookie attributes and the Origin check that backs them.

Both exist for one reason: the map is embedded as a cross-site iframe (the
RescueMate Lagebild on uni-hamburg.de framing map.skynet.coypu.org), where a
SameSite=Lax cookie is never stored. The invariants that make that work — None
implies Secure and Partitioned, and set/clear use identical attributes — are easy
to break by editing one of the two call sites, hence pinned here.
"""
import pytest
from starlette.responses import Response

from app.auth import SESSION_COOKIE, _cookie_kwargs, clear_session_cookie, set_session_cookie
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


def _cookie_header(fn) -> str:
    response = Response()
    fn(response)
    return response.headers["set-cookie"]


# --- attributes -----------------------------------------------------------

def test_none_forces_secure(cross_site):
    """Browsers reject SameSite=None without Secure, so it must not depend on the
    COOKIE_SECURE setting."""
    kwargs = _cookie_kwargs()
    assert kwargs["samesite"] == "none"
    assert kwargs["secure"] is True


def test_lax_keeps_secure_configurable(same_site):
    kwargs = _cookie_kwargs()
    assert kwargs["samesite"] == "lax"
    assert kwargs["secure"] is False


def test_partitioned_never_goes_through_starlette(cross_site):
    """Starlette's set_cookie(partitioned=True) raises below Python 3.14 and the
    backend image runs 3.11 — passing it would 500 every login, so the attribute
    must be appended to the raw header instead of handed to set_cookie."""
    assert "partitioned" not in _cookie_kwargs()


def test_cross_site_set_cookie_header(cross_site):
    header = _cookie_header(lambda r: set_session_cookie(r, "tok123"))
    assert f"{SESSION_COOKIE}=tok123" in header
    assert "SameSite=none" in header
    assert "Secure" in header
    assert "Partitioned" in header
    assert "HttpOnly" in header


def test_clear_matches_set_attributes(cross_site):
    """A partitioned cookie is a distinct cookie to the browser: logging out with
    different attributes would leave the session cookie in place."""
    set_header = _cookie_header(lambda r: set_session_cookie(r, "tok123"))
    clear_header = _cookie_header(clear_session_cookie)

    def attrs(header: str) -> set[str]:
        return {p.strip() for p in header.split(";")[1:] if not p.strip().startswith(("Max-Age", "expires"))}

    assert attrs(set_header) == attrs(clear_header)
    assert "Max-Age=0" in clear_header


def test_lax_cookie_is_not_partitioned(same_site):
    assert "Partitioned" not in _cookie_header(lambda r: set_session_cookie(r, "tok123"))


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
