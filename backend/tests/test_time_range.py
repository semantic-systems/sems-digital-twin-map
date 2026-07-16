"""
Time-window resolution. A custom since/until range takes precedence over a
preset time_window — and critically, providing ONLY a custom `until` still
discards the preset window entirely (no lower bound at all), which is easy to
get wrong, so it's pinned down explicitly here.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.routers.reports import _parse_iso, _resolve_time_range, _since_from_window


def test_since_from_window_unknown_or_none_returns_none():
    assert _since_from_window(None) is None
    assert _since_from_window("") is None
    assert _since_from_window("not_a_window") is None


@pytest.mark.parametrize("window,hours", [("1h", 1), ("6h", 6), ("1d", 24), ("3d", 72)])
def test_since_from_window_presets(window, hours):
    before = datetime.now(timezone.utc)
    result = _since_from_window(window)
    after = datetime.now(timezone.utc)
    assert before - timedelta(hours=hours) <= result <= after - timedelta(hours=hours)


def test_parse_iso_none_and_empty():
    assert _parse_iso(None) is None
    assert _parse_iso("") is None


def test_parse_iso_valid_string():
    dt = _parse_iso("2026-01-15T12:00:00+00:00")
    assert dt == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_iso_accepts_trailing_z():
    dt = _parse_iso("2026-01-15T12:00:00Z")
    assert dt == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_iso_invalid_string_returns_none():
    assert _parse_iso("not a date") is None


def test_resolve_time_range_no_args_returns_none_none():
    assert _resolve_time_range(None, None, None) == (None, None)


def test_resolve_time_range_preset_window_only():
    since, until = _resolve_time_range("1h", None, None)
    assert since is not None
    assert until is None


def test_resolve_time_range_custom_since_and_until_take_precedence_over_window():
    since, until = _resolve_time_range(
        "3d", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"
    )
    assert since == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert until == datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_resolve_time_range_custom_until_only_drops_the_preset_window_lower_bound():
    # Providing ONLY `until` still bypasses time_window entirely -- the result
    # has NO lower bound at all, not "window's since + custom until". This is
    # the exact branch that's easy to get wrong when refactoring.
    since, until = _resolve_time_range("1h", None, "2026-01-02T00:00:00Z")
    assert since is None
    assert until == datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_resolve_time_range_invalid_custom_strings_fall_back_to_window():
    since, until = _resolve_time_range("1h", "garbage", "also garbage")
    assert since is not None  # falls back to the 1h preset
    assert until is None
