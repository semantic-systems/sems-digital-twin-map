from __future__ import annotations

"""
layer_service.py
----------------
Converts Layer / Scenario ORM objects into GeoJSON FeatureCollections
suitable for consumption by a Leaflet-based frontend.
"""

import traceback
from typing import Any

from shapely.geometry import mapping
from shapely.wkb import loads as wkb_loads
from sqlalchemy.orm import Session

from ..db import Feature, FeatureSet, Layer, Scenario, Style


# ---------------------------------------------------------------------------
# Style → Leaflet dict
# ---------------------------------------------------------------------------

def style_to_leaflet(style: Style) -> dict[str, Any]:
    """Convert a Style ORM row to a Leaflet-compatible style dict."""
    return {
        "color": style.border_color,
        "weight": style.line_weight,
        "opacity": style.opacity,
        "fill": style.fill,
        "fillColor": style.area_color,
        "fillOpacity": style.fill_opacity,
        "stroke": style.stroke,
        "dashArray": style.dash_array,
        "marker_icon": style.marker_icon,
        "marker_color": style.marker_color,
    }


# ---------------------------------------------------------------------------
# Feature → GeoJSON Feature dict
# ---------------------------------------------------------------------------

def feature_to_geojson(feature: Feature) -> dict[str, Any]:
    """
    Convert a Feature ORM row to a GeoJSON Feature dict.

    Uses shapely to deserialise the PostGIS geometry stored as WKB.
    Raises ValueError if the geometry cannot be parsed.
    """
    try:
        geom = wkb_loads(bytes(feature.geometry.data), hex=True)
        geom_dict = mapping(geom)
    except Exception as exc:
        raise ValueError(
            f"Cannot serialise geometry for Feature(id={feature.id}): {exc}"
        ) from exc

    feature_set: FeatureSet = feature.feature_set
    style: Style = feature_set.style

    properties: dict[str, Any] = dict(feature.properties or {})
    properties["_feature_id"] = feature.id
    properties["_feature_set_name"] = feature_set.name
    properties["_style"] = style_to_leaflet(style)

    return {
        "type": "Feature",
        "id": feature.id,
        "geometry": geom_dict,
        "properties": properties,
    }


# ---------------------------------------------------------------------------
# Layer → GeoJSON FeatureCollection
# ---------------------------------------------------------------------------

def layer_to_geojson(layer_id: int, session: Session) -> dict[str, Any]:
    """
    Return a GeoJSON FeatureCollection containing all features that belong
    to the given layer (across all its FeatureSets).
    Features whose geometry cannot be serialised are silently skipped.
    """
    layer: Layer | None = session.query(Layer).filter(Layer.id == layer_id).first()
    if layer is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "layer_id": layer_id,
            "layer_name": None,
        }

    geojson_features: list[dict] = []
    for feature_set in layer.feature_sets:
        for feature in feature_set.features:
            try:
                geojson_features.append(feature_to_geojson(feature))
            except ValueError:
                traceback.print_exc()
                continue

    return {
        "type": "FeatureCollection",
        "features": geojson_features,
        "layer_id": layer_id,
        "layer_name": layer.name,
    }


# ---------------------------------------------------------------------------
# Scenario → GeoJSON FeatureCollection
# ---------------------------------------------------------------------------

def scenario_to_geojson(scenario_id: int, session: Session) -> dict[str, Any]:
    """
    Return a GeoJSON FeatureCollection containing all features that belong
    to the given scenario.
    Features whose geometry cannot be serialised are silently skipped.
    """
    scenario: Scenario | None = (
        session.query(Scenario).filter(Scenario.id == scenario_id).first()
    )
    if scenario is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "scenario_id": scenario_id,
            "scenario_name": None,
        }

    geojson_features: list[dict] = []
    for feature_set in scenario.feature_sets:
        for feature in feature_set.features:
            try:
                geojson_features.append(feature_to_geojson(feature))
            except ValueError:
                traceback.print_exc()
                continue

    return {
        "type": "FeatureCollection",
        "features": geojson_features,
        "scenario_id": scenario_id,
        "scenario_name": scenario.name,
    }


# ---------------------------------------------------------------------------
# List helpers
# ---------------------------------------------------------------------------

def get_layers(session: Session) -> list[dict[str, Any]]:
    """Return [{id, name}] for all layers."""
    layers: list[Layer] = session.query(Layer).order_by(Layer.id).all()
    return [{"id": layer.id, "name": layer.name} for layer in layers]


def get_scenarios(session: Session) -> list[dict[str, Any]]:
    """Return [{id, name, description}] for all scenarios."""
    scenarios: list[Scenario] = (
        session.query(Scenario).order_by(Scenario.id).all()
    )
    return [
        {"id": s.id, "name": s.name, "description": s.description}
        for s in scenarios
    ]
