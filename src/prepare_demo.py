#!/usr/bin/env python3
"""
Prepare demo data by resolving OSM locations via Nominatim.

Run once from the src/ directory before starting the app in demo mode:

    python prepare_demo.py

Writes src/data/demo_data.json with all report fields pre-filled,
including georeferenced location dicts. seed_demo_data() reads this
file at runtime instead of calling Nominatim.
"""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

# Allow imports from src/
sys.path.insert(0, os.path.dirname(__file__))

from data.build import DEMO_REPORTS

load_dotenv()

NOMINATIM_URL = os.environ.get('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
OUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'demo_data.json')


# ---------------------------------------------------------------------------
# Nominatim helpers
# ---------------------------------------------------------------------------

def _resolve_osm(name: str) -> dict | None:
    """Query Nominatim for a Hamburg place name. Returns a location dict or None."""
    url = NOMINATIM_URL.rstrip('/') + '/search'
    try:
        r = requests.get(
            url,
            params={'q': f'{name}, Hamburg', 'format': 'json', 'limit': 1, 'polygon_geojson': 1},
            headers={'User-Agent': 'sems-digital-twin-demo/1.0', 'Accept': 'application/json'},
            timeout=10,
        )
        r.raise_for_status()
        body = r.text.strip()
        if not body or body[0] not in '[{':
            print(f"  ✗ {name!r}: Nominatim returned non-JSON — {body[:80]!r}")
            return None
        results = r.json()
    except Exception as e:
        print(f"  ✗ {name!r}: request failed — {e}")
        return None

    if not results:
        print(f"  ✗ {name!r}: no results")
        return None

    hit = results[0]
    return {
        'osm_id': hit.get('osm_id'),
        'lat': float(hit['lat']),
        'lon': float(hit['lon']),
        'name': name,
        'mention': name,
        'display_name': hit.get('display_name', name),
        'polygon': hit.get('geojson'),
    }


def _build_locs(loc_mentions: list, osm_cache: dict) -> list:
    """Convert (loc_type, name) tuples to resolved location dicts."""
    locs = []
    for loc_type, name in loc_mentions:
        if loc_type == 'georef':
            locs.append(osm_cache.get(name) or {'mention': name})
        elif loc_type == 'mention':
            locs.append({'mention': name})
    return locs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    unique_georef = sorted({
        name
        for *_, loc_mentions in DEMO_REPORTS
        for loc_type, name in loc_mentions
        if loc_type == 'georef'
    })

    print(f"Resolving {len(unique_georef)} unique place names via Nominatim ({NOMINATIM_URL})…")
    osm_cache: dict[str, dict] = {}
    for i, place in enumerate(unique_georef):
        if i > 0:
            time.sleep(1.1)  # respect Nominatim's 1 req/s limit
        result = _resolve_osm(place)
        if result:
            osm_cache[place] = result
            print(f"  ✓ {place} → {result['lat']:.4f}, {result['lon']:.4f}")

    # Build fully resolved report list (no timestamps — added fresh at seed time)
    records = []But
    for i, (text, platform, event_type, relevance, author, loc_mentions) in enumerate(DEMO_REPORTS):
        locs = _build_locs(loc_mentions, osm_cache)
        records.append({
            'identifier': f'demo-{i}',
            'text': text,
            'platform': platform,
            'event_type': event_type,
            'relevance': relevance,
            'author': author or '',
            'url': f'https://example.com/demo/{i}',
            'locations': locs,
        })

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    georeffed = sum(1 for r in records for loc in r['locations'] if 'osm_id' in loc)
    mentions  = sum(1 for r in records for loc in r['locations'] if 'osm_id' not in loc)
    no_locs   = sum(1 for r in records if not r['locations'])

    print(f"\nWrote {len(records)} records → {OUT_PATH}")
    print(f"Locations: {georeffed} georeferenced, {mentions} mention-only, {no_locs} none")


if __name__ == '__main__':
    main()
