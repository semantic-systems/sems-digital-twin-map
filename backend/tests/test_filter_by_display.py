"""
filter_by_display is the Python-level post-query filter path (used whenever the
SQL-level LIMIT can't be pushed down). It re-derives a report's location status
(localized/pending/unlocalized) using the user's OWN overridden locations
(user_locs_map) when present, instead of the report's raw stored locations —
this override is easy to silently regress, so it's tested explicitly.

Report is a plain SQLAlchemy declarative model; constructing an instance
in-memory (no session.add/commit) triggers no database access at all.
"""
from app.db import Report
from app.services.report_service import filter_by_display


def make_report(id, locations=None, author=""):
    return Report(id=id, locations=locations, author=author, text="", url="",
                  platform="mastodon", timestamp=None, event_type="", relevance="high")


def test_hide_seen_excludes_seen_reports():
    reports = [make_report(1), make_report(2)]
    result = filter_by_display(
        reports, loc_filter=None, seen_ids={1}, flagged_authors=set(),
        user_locs_map={}, hide_seen=True, hide_flagged=False, hide_unflagged=False,
    )
    assert [r.id for r in result] == [2]


def test_show_hidden_keeps_seen_reports():
    reports = [make_report(1), make_report(2)]
    result = filter_by_display(
        reports, loc_filter=None, seen_ids={1}, flagged_authors=set(),
        user_locs_map={}, hide_seen=False, hide_flagged=False, hide_unflagged=False,
    )
    assert {r.id for r in result} == {1, 2}


def test_hide_flagged_excludes_flagged_authors():
    reports = [make_report(1, author="alice"), make_report(2, author="bob")]
    result = filter_by_display(
        reports, loc_filter=None, seen_ids=set(), flagged_authors={"alice"},
        user_locs_map={}, hide_seen=False, hide_flagged=True, hide_unflagged=False,
    )
    assert [r.id for r in result] == [2]


def test_hide_unflagged_keeps_only_flagged_authors():
    reports = [make_report(1, author="alice"), make_report(2, author="bob")]
    result = filter_by_display(
        reports, loc_filter=None, seen_ids=set(), flagged_authors={"alice"},
        user_locs_map={}, hide_seen=False, hide_flagged=False, hide_unflagged=True,
    )
    assert [r.id for r in result] == [1]


def test_loc_filter_localized_requires_osm_id():
    reports = [
        make_report(1, locations=[{"osm_id": "123"}]),      # localized
        make_report(2, locations=[{"mention": "somewhere"}]),  # pending
        make_report(3, locations=[]),                        # unlocalized
    ]
    result = filter_by_display(
        reports, loc_filter=["localized"], seen_ids=set(), flagged_authors=set(),
        user_locs_map={}, hide_seen=False, hide_flagged=False, hide_unflagged=False,
    )
    assert [r.id for r in result] == [1]


def test_loc_filter_pending_is_non_empty_without_osm_id():
    reports = [
        make_report(1, locations=[{"osm_id": "123"}]),
        make_report(2, locations=[{"mention": "somewhere"}]),
        make_report(3, locations=[]),
    ]
    result = filter_by_display(
        reports, loc_filter=["pending"], seen_ids=set(), flagged_authors=set(),
        user_locs_map={}, hide_seen=False, hide_flagged=False, hide_unflagged=False,
    )
    assert [r.id for r in result] == [2]


def test_loc_filter_unlocalized_is_empty_or_none():
    reports = [
        make_report(1, locations=[{"osm_id": "123"}]),
        make_report(2, locations=None),
        make_report(3, locations=[]),
    ]
    result = filter_by_display(
        reports, loc_filter=["unlocalized"], seen_ids=set(), flagged_authors=set(),
        user_locs_map={}, hide_seen=False, hide_flagged=False, hide_unflagged=False,
    )
    assert {r.id for r in result} == {2, 3}


def test_loc_filter_full_set_means_no_restriction():
    reports = [make_report(1, locations=[{"osm_id": "1"}]), make_report(2, locations=[])]
    result = filter_by_display(
        reports, loc_filter=["localized", "pending", "unlocalized"],
        seen_ids=set(), flagged_authors=set(), user_locs_map={},
        hide_seen=False, hide_flagged=False, hide_unflagged=False,
    )
    assert {r.id for r in result} == {1, 2}


def test_loc_filter_none_means_no_restriction():
    reports = [make_report(1, locations=[{"osm_id": "1"}]), make_report(2, locations=[])]
    result = filter_by_display(
        reports, loc_filter=None, seen_ids=set(), flagged_authors=set(),
        user_locs_map={}, hide_seen=False, hide_flagged=False, hide_unflagged=False,
    )
    assert {r.id for r in result} == {1, 2}


def test_user_locs_map_override_takes_precedence_over_raw_locations():
    # Report's raw stored locations are pending (no osm_id), but the user has
    # overridden them with a geocoded (localized) location. The override must
    # win -- this is the exact mechanism that keeps dots/polygons in sync with
    # what a user has pinned via the map UI.
    reports = [make_report(1, locations=[{"mention": "somewhere"}])]
    result = filter_by_display(
        reports, loc_filter=["localized"], seen_ids=set(), flagged_authors=set(),
        user_locs_map={1: [{"osm_id": "999"}]},
        hide_seen=False, hide_flagged=False, hide_unflagged=False,
    )
    assert [r.id for r in result] == [1]

    # And the inverse: filtering for "pending" now excludes it, since the
    # override made it localized.
    result2 = filter_by_display(
        reports, loc_filter=["pending"], seen_ids=set(), flagged_authors=set(),
        user_locs_map={1: [{"osm_id": "999"}]},
        hide_seen=False, hide_flagged=False, hide_unflagged=False,
    )
    assert result2 == []


def test_filters_compose_with_and():
    reports = [
        make_report(1, locations=[{"osm_id": "1"}], author="alice"),
        make_report(2, locations=[{"osm_id": "2"}], author="bob"),
    ]
    result = filter_by_display(
        reports, loc_filter=["localized"], seen_ids={2}, flagged_authors={"alice"},
        user_locs_map={}, hide_seen=True, hide_flagged=True, hide_unflagged=False,
    )
    # report 1 is localized but flagged (alice) -> excluded by hide_flagged
    # report 2 is localized and unflagged, but seen -> excluded by hide_seen
    assert result == []
