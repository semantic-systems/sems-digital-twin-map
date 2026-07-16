from __future__ import annotations

from typing import Any

import requests
from fastapi import APIRouter, Query

from ..config import settings

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


@router.get("/nominatim")
def nominatim_search(
    q: str = Query(..., description="Search string"),
    limit: int = Query(7, ge=1, le=50),
) -> list[dict[str, Any]]:
    """
    Proxy to Nominatim /search.
    Requests polygon_geojson=1 and returns a cleaned list of results.
    Returns [] on any error so the frontend can degrade gracefully.
    """
    try:
        response = requests.get(
            f"{settings.NOMINATIM_URL}/search",
            params={
                "q": q,
                "format": "json",
                "limit": limit,
                "polygon_geojson": 1,
                "addressdetails": 1,
            },
            headers={"User-Agent": "sems-digital-twin-map/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        raw: list[dict] = response.json()
    except Exception:
        return []

    results: list[dict[str, Any]] = []
    for item in raw:
        results.append(
            {
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "display_name": item.get("display_name"),
                "osm_id": str(item.get("osm_id", "")),
                "osm_type": item.get("osm_type"),
                "boundingbox": item.get("boundingbox"),
                "geojson": item.get("geojson"),
            }
        )

    return results
