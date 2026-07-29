"""
normalize_filters collapses an "everything selected" filter to None (no
restriction). None means "no filter"; an empty list from the caller also means
"no filter" for events/relevance (collapsed) — but NOT for platforms, which
have no such collapse (see test_platform_empty_list_means_no_filter vs.
test_platform_never_collapses_on_full_selection below — this asymmetry is
existing, intentional behavior, not a bug).
"""
from app.services.report_service import (
    ALL_EVENT_TYPES,
    ALL_RELEVANCE_TYPES,
    normalize_filters,
)


def test_all_none_passes_through_as_none():
    assert normalize_filters(None, None, None) == (None, None, None, None)


def test_empty_lists_collapse_to_none():
    assert normalize_filters([], [], [], []) == (None, None, None, None)


def test_platform_subset_is_kept_verbatim():
    eff_platform, _, _, _ = normalize_filters(["bluesky", "mastodon"], None, None)
    assert eff_platform == ["bluesky", "mastodon"]


def test_platform_never_collapses_on_full_selection():
    # Unlike events/relevance, platforms have no "all selected -> None" collapse:
    # passing every known platform still returns them as an explicit list.
    from app.services.report_service import ALL_PLATFORMS
    eff_platform, _, _, _ = normalize_filters(list(ALL_PLATFORMS), None, None)
    assert eff_platform == list(ALL_PLATFORMS)


def test_event_type_subset_is_kept():
    _, eff_events, _, _ = normalize_filters(None, ["Warnungen & Hinweise"], None)
    assert eff_events == ["Warnungen & Hinweise"]


def test_event_type_full_selection_collapses_to_none():
    _, eff_events, _, _ = normalize_filters(None, list(ALL_EVENT_TYPES), None)
    assert eff_events is None


def test_event_type_frontend_list_without_irrelevant_does_not_collapse():
    # The frontend never offers "Irrelevant" as a selectable event type, so its
    # "select all" can never be a superset of the backend's ALL_EVENT_TYPES
    # (which includes "Irrelevant"). Selecting all 11 frontend-visible types is
    # therefore NOT treated as "no filter" — it still explicitly excludes
    # "Irrelevant"-only reports. This is today's real, if subtle, behavior.
    frontend_all = [e for e in ALL_EVENT_TYPES if e != "Irrelevant"]
    assert len(frontend_all) == len(ALL_EVENT_TYPES) - 1
    _, eff_events, _, _ = normalize_filters(None, frontend_all, None)
    assert eff_events == frontend_all


def test_relevance_subset_is_kept():
    _, _, eff_relevance, _ = normalize_filters(None, None, ["high", "medium"])
    assert eff_relevance == ["high", "medium"]


def test_relevance_full_selection_collapses_to_none():
    _, _, eff_relevance, _ = normalize_filters(None, None, list(ALL_RELEVANCE_TYPES))
    assert eff_relevance is None


def test_relevance_superset_also_collapses_to_none():
    # normalize_filters uses >= (superset-or-equal), so extra/unknown values
    # alongside the full set still collapse.
    _, _, eff_relevance, _ = normalize_filters(
        None, None, [*ALL_RELEVANCE_TYPES, "made_up_value"]
    )
    assert eff_relevance is None


def test_taxonomy_empty_is_none_and_groups_are_parsed():
    # Taxonomy has no "ALL" set — no groups is treated as None (no filter).
    _, _, _, eff_taxonomy = normalize_filters(None, None, None, [])
    assert eff_taxonomy is None

    # One value per saved query, its labels comma-separated: the grouping is what
    # lets build_report_query OR whole queries together instead of merging their
    # labels into a single over-narrow facet-AND.
    _, _, _, eff_taxonomy = normalize_filters(
        None, None, None, ["hazard_type.natural_hydrological.flood"]
    )
    assert eff_taxonomy == [["hazard_type.natural_hydrological.flood"]]

    _, _, _, eff_taxonomy = normalize_filters(
        None,
        None,
        None,
        ["hazard_type.natural_hydrological.flood, affected_living_being.human",
         "action_type.search_and_rescue"],
    )
    assert eff_taxonomy == [
        ["hazard_type.natural_hydrological.flood", "affected_living_being.human"],
        ["action_type.search_and_rescue"],
    ]

    # Entries that carry no usable label are dropped, not turned into empty groups
    # (an empty group would AND to "match nothing" and silently blank the map).
    _, _, _, eff_taxonomy = normalize_filters(None, None, None, ["", "  ,  "])
    assert eff_taxonomy is None
