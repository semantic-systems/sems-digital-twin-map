"""
OSM type spelling normalization. Photon returns short codes (R/N/W), Nominatim
returns long words (relation/node/way) — the same real-world entity can be
referenced either way, and a report can even carry both spellings for what is
the same OSM object (a real case seen in production: a district referenced via
both 'R' and 'relation'). These helpers exist so a polygon lookup catches both.
"""
from app.services.report_service import _alt_osm_type, _osm_keys_with_alts


def test_alt_osm_type_short_to_long():
    assert _alt_osm_type("R") == "relation"
    assert _alt_osm_type("N") == "node"
    assert _alt_osm_type("W") == "way"


def test_alt_osm_type_long_to_short():
    assert _alt_osm_type("relation") == "R"
    assert _alt_osm_type("node") == "N"
    assert _alt_osm_type("way") == "W"


def test_alt_osm_type_unknown_returns_none():
    assert _alt_osm_type("foo") is None
    assert _alt_osm_type("") is None


def test_osm_keys_with_alts_expands_short_to_include_long():
    expanded = set(_osm_keys_with_alts({("123", "R")}))
    assert expanded == {("123", "R"), ("123", "relation")}


def test_osm_keys_with_alts_expands_long_to_include_short():
    expanded = set(_osm_keys_with_alts({("123", "relation")}))
    assert expanded == {("123", "relation"), ("123", "R")}


def test_osm_keys_with_alts_unknown_type_not_duplicated():
    expanded = set(_osm_keys_with_alts({("123", "foo")}))
    assert expanded == {("123", "foo")}


def test_osm_keys_with_alts_expands_each_key_independently():
    expanded = set(_osm_keys_with_alts({("1", "R"), ("2", "way")}))
    assert expanded == {("1", "R"), ("1", "relation"), ("2", "way"), ("2", "W")}
