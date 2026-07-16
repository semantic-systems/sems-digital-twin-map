"""
_polygon_bbox computes [min_lat, max_lat, min_lon, max_lon] over a GeoJSON
geometry. This is the function whose frontend counterpart (locationExtent)
originally only read a polygon's first ring — silently shrinking a district's
suppression extent to a fragment and defeating containment suppression (the
Traunstein bug). These tests pin down the correct, full-geometry behavior here.
"""
from app.services.report_service import _polygon_bbox


def test_polygon_single_ring():
    geo = {"type": "Polygon", "coordinates": [[[10, 50], [11, 50], [11, 51], [10, 51], [10, 50]]]}
    assert _polygon_bbox(geo) == [50, 51, 10, 11]


def test_polygon_bbox_spans_all_rings_not_just_the_first():
    # A polygon with an outer ring AND a hole (inner ring) far outside the
    # outer ring's extent — the bbox must cover both, not just ring[0].
    outer = [[10, 50], [11, 50], [11, 51], [10, 51], [10, 50]]
    hole_far_away = [[20, 60], [21, 60], [21, 61], [20, 61], [20, 60]]
    geo = {"type": "Polygon", "coordinates": [outer, hole_far_away]}
    assert _polygon_bbox(geo) == [50, 61, 10, 21]


def test_multipolygon_spans_every_polygon_and_ring():
    geo = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            [[[5, 5], [6, 5], [6, 6], [5, 6], [5, 5]]],
        ],
    }
    assert _polygon_bbox(geo) == [0, 6, 0, 6]


def test_linestring_bbox():
    geo = {"type": "LineString", "coordinates": [[10, 50], [12, 52], [11, 49]]}
    assert _polygon_bbox(geo) == [49, 52, 10, 12]


def test_multilinestring_bbox_spans_all_lines():
    geo = {
        "type": "MultiLineString",
        "coordinates": [[[0, 0], [1, 1]], [[5, 5], [6, 6]]],
    }
    assert _polygon_bbox(geo) == [0, 6, 0, 6]


def test_point_geometry_returns_none():
    # Deliberately unsupported: stored point coordinate order is unreliable,
    # and a node's authoritative position is the dot's own lat/lon instead.
    geo = {"type": "Point", "coordinates": [10, 50]}
    assert _polygon_bbox(geo) is None


def test_unknown_geometry_type_returns_none():
    geo = {"type": "GeometryCollection", "coordinates": []}
    assert _polygon_bbox(geo) is None


def test_missing_coordinates_returns_none():
    assert _polygon_bbox({"type": "Polygon"}) is None
    assert _polygon_bbox({"type": "Polygon", "coordinates": []}) is None


def test_empty_rings_return_none():
    assert _polygon_bbox({"type": "Polygon", "coordinates": [[]]}) is None
