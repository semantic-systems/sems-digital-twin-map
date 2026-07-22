import os
from collections import defaultdict

import requests
import time
from datetime import datetime, timedelta, timezone

from shapely import polygonize, GeometryCollection, LineString, wkt
from shapely.geometry import mapping
from SPARQLWrapper import SPARQLWrapper
from data.connect import autoconnect_db
from data.model import LocationPolygon, Report

import random   # can be removed later


SPARQL_ENDPOINT = os.getenv('SPARQL_ENDPOINT', '')
if not SPARQL_ENDPOINT:
    raise ValueError("SPARQL_ENDPOINT environment variable is not set.")


BOUNDING_BOX = os.getenv('BOUNDING_BOX', '')

# how long to wait between requests (in seconds)
REQUEST_DELAY = 10

# how long to wait before timing out a request (in seconds)
TIMEOUT_DELAY = 300            # 5 minutes

# set to True to print more information
VERBOSE = True

# user agent for the requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# the API URL
API_URL = 'http://python-social-media-retriever-api:5000/search'

# what text to use from posts from each platform
TEXT_FIELD = {
    "bluesky": "text",
    "mastodon": "text",
    "reddit": "title",
    "youtube": "title",
    "twitter": "text",
    "rss": "title"
}

# the search parameters
SEARCH_QUERY = 'hamburg sturm'
SEARCH_LIMIT = 25
SEARCH_SUBREDDITS = ['hamburg', 'de']
SEARCH_PLATFORMS = ['mastodon', 'bluesky', 'reddit', 'youtube', 'rss']
SEARCH_MANDATORY_KEYWORDS = ['hamburg']
SEARCH_OPTIONAL_KEYWORDS = ['sturm', 'storm', 'flut', 'flood', 'unwetter', 'regen', 'rain']
SEARCH_N_KEYWORDS = 1
SEARCH_W_REGEX = '.*(hamburg).*'
SEARCH_B_REGEX = '.*(berlin).*'
SEARCH_LOOK_BACK = 30    # how many minutes to look back

sparql = SPARQLWrapper(SPARQL_ENDPOINT)

def get_keycloak_token():
    KEYCLOAK_URL = "https://node-1.net.uhh.rescue-mate.de/auth"
    REALM = "master"
    CLIENT_ID = "uhh"

    USERNAME = os.getenv('USERNAME', '')
    PASSWORD = os.getenv('PASSWORD', '')

    token_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"

    data = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": USERNAME,
        "password": PASSWORD,
        # Optional, falls dein Client ein Secret verlangt:
        # "client_secret": "dein-secret",
    }

    response = requests.post(token_url, data=data)
    response.raise_for_status()
    token = response.json()["access_token"]

    return token

def wkt_to_geojson(wkt_str: str):
    # Parse WKT
    geom = wkt.loads(wkt_str)

    # Convert to GeoJSON dictionary
    geojson_dict = mapping(geom)
    return geojson_dict

def _run_sparql_raise(query: str, auth_header: str) -> list:
    """Like _run_sparql but propagates failures instead of swallowing them.
    Used where a caller needs to tell a real query failure apart from a
    legitimately empty result set (e.g. the WKT batch retry/bisection below)."""
    sparql.setQuery(query)
    sparql.setReturnFormat('json')
    sparql.setMethod('POST')
    sparql.addCustomHttpHeader("User-Agent", USER_AGENT)
    sparql.addCustomHttpHeader("Authorization", auth_header)
    return sparql.query().convert()['results']['bindings']


def _run_sparql(query: str, auth_header: str) -> list:
    try:
        return _run_sparql_raise(query, auth_header)
    except Exception as e:
        status = getattr(getattr(e, 'response', None), 'status', None)
        print(f"Error fetching data from SPARQL endpoint (HTTP {status}): {e}", flush=True)
        return []


# Geometry URIs whose WKT fetch failed even in isolation (single-URI query),
# remembered for the process lifetime. Without this, a permanently broken
# geometry gets re-tried — and its batch re-bisected — on EVERY ingestion cycle
# for as long as any post in the search window references it, spamming the log
# with the same failure. Reset on restart, so a transient server-side problem
# still gets another chance eventually.
_unfetchable_geometry_uris: set = set()


def _fetch_wkt_batch(uris: list, auth_header: str) -> dict:
    """Fetch WKT geometries for a batch of location URIs.

    The WKT is selected as STR(?wkt), not raw ?wkt: Virtuoso's result-set
    serializer for virtrdf:Geometry-typed literals fails with 'SR578: The
    expected result length of wide string is too large' on large geometries
    (observed on a 4.3 MB MULTIPOLYGON) and 500s the whole response. STR()
    coerces the literal to a plain string inside the engine, bypassing that
    serializer — verified against the live endpoint: the same URI that 500s
    as raw ?wkt returns its full WKT via STR(?wkt).

    Should a query still fail for another reason, one bad URI fails the whole
    VALUES batch, so on failure we bisect and retry each half independently —
    isolating and skipping just the offending URI(s) (remembered in
    _unfetchable_geometry_uris) instead of losing every geometry in the batch."""
    uris = [u for u in uris if u not in _unfetchable_geometry_uris]
    if not uris:
        return {}

    loc_values = ' '.join(f'<{uri}>' for uri in uris)
    wkt_query = f"""
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        SELECT ?location (STR(?wkt) AS ?wkt_str) {{
            GRAPH <{SOCIAL_MEDIA_GRAPH}> {{
                VALUES ?location {{ {loc_values} }}
                ?location geo:hasGeometry ?geom .
                ?geom geo:asWKT ?wkt .
            }}
        }}
    """
    try:
        bindings = _run_sparql_raise(wkt_query, auth_header)
    except Exception as e:
        if len(uris) == 1:
            _unfetchable_geometry_uris.add(uris[0])
            print(f"Skipping unfetchable geometry for {uris[0]} (won't retry until restart): {e}", flush=True)
            return {}
        mid = len(uris) // 2
        result = _fetch_wkt_batch(uris[:mid], auth_header)
        result.update(_fetch_wkt_batch(uris[mid:], auth_header))
        return result

    result = {}
    for binding in bindings:
        loc_uri = binding['location']['value']
        try:
            result[loc_uri] = wkt_to_geojson(binding['wkt_str']['value'])
        except Exception as e:
            print(f"Skipping unparsable WKT for {loc_uri}: {e}", flush=True)
    return result


LOCATION_BATCH_SIZE = 50  # Virtuoso rejects VALUES clauses with too many URIs

# The endpoint hosts many unrelated datasets (old social-media snapshots, demo
# datasets, deich/sensor data, ...). Every query below must be scoped to this
# graph explicitly — without a GRAPH clause, Virtuoso matches across ALL of
# them, silently mixing in ~1M stale posts from the retired social_media_v2
# dataset plus whatever else happens to live on the endpoint.
SOCIAL_MEDIA_GRAPH = 'http://rescue-mate.de/datasets/social_media_data'

# Post-level statuses that indicate the classifier failed to produce a
# category/relevance for a post at all (so it would otherwise never appear in
# the results — see the UNION in posts_query below).
FAILED_POST_STATUSES = ('rm:error', 'rm:no_text')

RELEVANT_CATEGORIES = ' '.join(f'<http://rescue-mate.de/resource/{c}>' for c in [
    'affected_individual', 'caution_and_advice', 'displaced_and_evacuations',
    'donation_and_volunteering', 'infrastructure_and_utilities_damage',
    'injured_or_dead_people', 'missing_and_found_people', 'requests_or_needs',
    'response_efforts', 'sympathy_and_support', 'other_emergency',
])


def fetch_social_media_posts(search_since: datetime, search_until: datetime | None = None):
    """Fetch posts from RescueMate KG using two queries: posts then locations."""

    auth_header = f"Bearer {get_keycloak_token()}"
    search_since_str = search_since.isoformat().replace('+00:00', 'Z')
    until_filter = f'FILTER (?date <= "{search_until.isoformat().replace("+00:00", "Z")}"^^xsd:dateTime)' if search_until else ''

    # Query 1: post metadata only — no geometry joins.
    # A post is returned if EITHER it has a relevant category+relevance (the normal
    # case) OR its processing status indicates the classifier failed outright (so it
    # would otherwise have no category/relevance and never appear here at all).
    # NOTE: ?postStatus must be bound as a real triple pattern inside each UNION
    # branch, NOT via a shared outer OPTIONAL + a bare FILTER in the second branch —
    # that shape makes Virtuoso's query planner drastically over-estimate the cost
    # and return a 500 (verified against the live endpoint). Binding it separately
    # per branch avoids that.
    posts_query = f"""
        PREFIX rm: <http://rescue-mate.de/resource/>
        PREFIX rmo: <http://rescue-mate.de/ontology/>
        PREFIX schema: <http://schema.org/>
        SELECT ?post ?text ?date ?category ?predictedRelevance ?url ?user ?username ?platform ?user_identifier ?geoRecognitionStatus ?postStatus  {{
            GRAPH <{SOCIAL_MEDIA_GRAPH}> {{
                ?post a rmo:SocialMediaPost ;
                    schema:text ?text ;
                    schema:dateCreated ?date .
                {{
                    VALUES ?category {{ {RELEVANT_CATEGORIES} }}
                    ?post rmo:hasDetectedCategory ?category ;
                        rm:predictedRelevance ?predictedRelevance .
                    ?post rm:eventPredictionStatus ?postStatus .
                    ?post rm:geoRecognitionStatus ?geoRecognitionStatus .
                }}
                UNION
                {{
                    ?post rm:eventPredictionStatus ?postStatus .
                    ?post rm:geoRecognitionStatus ?geoRecognitionStatus .
                    ?post rmo:hasDetectedCategory ?category ;
                        rm:predictedRelevance ?predictedRelevance .
                    FILTER (?postStatus IN ({', '.join(FAILED_POST_STATUSES)}))
                }}
                FILTER (?date > "{search_since_str}"^^xsd:dateTime)
                {until_filter}
                OPTIONAL {{ ?post schema:url ?url }}
                OPTIONAL {{
                    ?post schema:author ?user .
                    OPTIONAL {{ ?user schema:name ?username }}
                    OPTIONAL {{ ?user rm:socialMediaServiceName ?platform }}
                    OPTIONAL {{ ?user schema:identifier ?user_identifier }}
                }}
            }}
        }}
    """

    bindings = _run_sparql(posts_query, auth_header)
    if not bindings:
        return []

    posts = {}
    post_uris = {}
    for result in bindings:
        post_uri = result['post']['value']
        post_id = post_uri.split('/')[-1]
        post_uris[post_id] = post_uri
        raw_category = result.get('category', {}).get('value', '')
        if post_id not in posts:
            posts[post_id] = {
                'id': post_id,
                'text': result['text']['value'],
                'timestamp': result['date']['value'],
                'platform': result.get('platform', {}).get('value', '').split('/')[-1],
                'url': result.get('url', {'value': ''})['value'],
                'event_types': [raw_category] if raw_category else [],
                'relevance': result.get('predictedRelevance', {}).get('value', 'http://rescue-mate.de/resource/none'),
                'processing_status': result['postStatus']['value'].split('/')[-1] or 'ok',
                'geo_recognition_status': result['geoRecognitionStatus']['value'].split('/')[-1] or 'ok',
                'geo_linked_entities': [],
                'author': (
                    result.get('username', {}).get('value') or
                    result.get('user_identifier', {}).get('value') or
                    result.get('user', {}).get('value', '').split('/')[-1]
                ),
            }
        elif raw_category and raw_category not in posts[post_id]['event_types']:
            posts[post_id]['event_types'].append(raw_category)

    if VERBOSE:
        print(f"Query 1: {len(posts)} posts in window", flush=True)


    # Query 2a: location metadata only (no geometry), batched to stay under Virtuoso's
    # VALUES clause size limit. Fetches lat/lon so we can bbox-filter before requesting WKT.
    post_uri_list = list(post_uris.values())
    bbox = tuple(map(float, BOUNDING_BOX.split(','))) if BOUNDING_BOX else None
    seen_mentions: dict[str, set] = defaultdict(set)
    in_bbox_locs: dict[str, dict] = {}          # location_uri -> metadata
    pending: list[tuple[str, str, str]] = []    # (post_id, mention, location_uri)

    for i in range(0, len(post_uri_list), LOCATION_BATCH_SIZE):
        batch_values = ' '.join(f'<{uri}>' for uri in post_uri_list[i:i + LOCATION_BATCH_SIZE])
        loc_meta_query = f"""
            PREFIX rm: <http://rescue-mate.de/resource/>
            PREFIX obo: <http://purl.obolibrary.org/obo/>
            PREFIX schema: <http://schema.org/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?post ?location_mention_surface_form ?location ?osm_type ?osm_id ?lat ?lon ?name ?locStatus {{
                GRAPH <{SOCIAL_MEDIA_GRAPH}> {{
                    VALUES ?post {{ {batch_values} }}
                    ?post rm:hasMentionedLocation ?location_mention .
                    ?location_mention schema:text ?location_mention_surface_form .
                    ?location_mention rm:geoLinkingStatus ?locStatus .
                    OPTIONAL {{
                        ?location_mention obo:IAO_0000136 ?location .
                        ?location rm:osm_type ?osm_type ;
                            rm:osm_id ?osm_id ;
                            rm:latitude ?lat ;
                            rm:longitude ?lon ;
                            rdfs:label ?name .
                    }}
                }}
            }}
        """
        for result in _run_sparql(loc_meta_query, auth_header):
            post_id = result['post']['value'].split('/')[-1]
            mention = result.get('location_mention_surface_form', {}).get('value')
            if not mention or mention in seen_mentions[post_id]:
                continue
            seen_mentions[post_id].add(mention)

            # 'ok' with no resolved location shouldn't normally happen, but falls back
            # to 'no_candidates' (matching pre-status silent-drop behavior) rather than
            # masking it as a clean 'ok'.
            loc_status = result['locStatus']['value'].split('/')[-1] or 'no_candidates'

            loc_uri = result.get('location', {}).get('value')
            if not loc_uri or 'osm_id' not in result:
                posts[post_id]['geo_linked_entities'].append({'mention': mention, 'location': None, 'status': loc_status})
                continue

            lat = float(result['lat']['value'])
            lon = float(result['lon']['value'])
            if bbox:
                min_lon, min_lat, max_lon, max_lat = bbox
                if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                    posts[post_id]['geo_linked_entities'].append({'mention': mention, 'location': None, 'status': loc_status})
                    continue

            in_bbox_locs[loc_uri] = {
                'osm_type': result['osm_type']['value'],
                'osm_id': int(result['osm_id']['value']),
                'lat': lat,
                'lon': lon,
                'name': result['name']['value'],
            }
            pending.append((post_id, mention, loc_uri))

    # Query 2b: WKT for in-bbox locations — check DB cache before hitting SPARQL.
    # LocationPolygon is populated by save_posts, so repeated locations (same OSM feature
    # referenced across many posts) are only ever fetched from SPARQL once.
    geojson_by_uri: dict[str, dict] = {}
    uncached_uris: list[str] = []

    if in_bbox_locs:
        _, session = autoconnect_db()
        try:
            unique_osm_ids = list({str(meta['osm_id']) for meta in in_bbox_locs.values()})
            cached_polys = {
                (r.osm_id, r.osm_type): r.polygon
                for r in session.query(LocationPolygon)
                    .filter(LocationPolygon.osm_id.in_(unique_osm_ids))
                    .all()
            }
        finally:
            session.close()

        for loc_uri, meta in in_bbox_locs.items():
            cached = cached_polys.get((str(meta['osm_id']), meta['osm_type']))
            if cached:
                geojson_by_uri[loc_uri] = cached
            else:
                uncached_uris.append(loc_uri)

    if uncached_uris:
        geojson_by_uri.update(_fetch_wkt_batch(uncached_uris, auth_header))

    if VERBOSE:
        n_cached = len(in_bbox_locs) - len(uncached_uris)
        print(f"Locations: {n_cached} from cache, {len(uncached_uris)} fetched from SPARQL", flush=True)

    for post_id, mention, loc_uri in pending:
        meta = in_bbox_locs[loc_uri]
        geo_linked_entity: dict = {'mention': mention, 'status': 'ok'}
        geojson = geojson_by_uri.get(loc_uri)
        if geojson:
            geo_linked_entity['location'] = {**meta, 'geojson': geojson, 'polygon': geojson}
        else:
            geo_linked_entity['location'] = None
        posts[post_id]['geo_linked_entities'].append(geo_linked_entity)

    if VERBOSE:
        print(f"Fetched {len(posts)} posts from SPARQL endpoint", flush=True)

    return posts.values()

event_mapping = {
    'http://rescue-mate.de/resource/not_humanitarian': 'Irrelevant',
    'http://rescue-mate.de/resource/affected_individual': 'Menschen betroffen',
    'http://rescue-mate.de/resource/caution_and_advice': 'Warnungen & Hinweise',
    'http://rescue-mate.de/resource/displaced_and_evacuations': 'Evakuierungen & Umsiedlungen',
    'http://rescue-mate.de/resource/donation_and_volunteering': 'Spenden & Freiwillige',
    'http://rescue-mate.de/resource/infrastructure_and_utilities_damage': 'Infrastruktur-Schäden',
    'http://rescue-mate.de/resource/injured_or_dead_people': 'Verletzte & Tote',
    'http://rescue-mate.de/resource/missing_and_found_people': 'Vermisste & Gefundene',
    'http://rescue-mate.de/resource/requests_or_needs': 'Bedarfe & Anfragen',
    'http://rescue-mate.de/resource/response_efforts': 'Einsatzmaßnahmen',
    'http://rescue-mate.de/resource/sympathy_and_support': 'Mitgefühl & Unterstützung',
    'http://rescue-mate.de/resource/other_emergency': 'Sonstiges',
    'http://rescue-mate.de/resource/unknown': 'unknown',
}

relevance_mapping = {
    'http://rescue-mate.de/resource/high': 'high',
    'http://rescue-mate.de/resource/medium': 'medium',
    'http://rescue-mate.de/resource/low': 'low',
    'http://rescue-mate.de/resource/none': 'none',
    'http://rescue-mate.de/resource/unknown': 'unknown',
}

def save_posts(posts: list):
    """Save the posts to the database"""

    engine, session = autoconnect_db()


    counter = 0

    posts = list(posts)
    existing_ids = {
        r.identifier
        for r in session.query(Report.identifier).filter(
            Report.identifier.in_([p['id'] for p in posts])
        ).all()
    }

    for json_post in posts:
        # Each post saves inside its own savepoint: one malformed post (e.g. an
        # unparsable timestamp or unexpected field shape) previously raised out
        # of the whole loop, silently dropping every post after it in the batch.
        try:
            with session.begin_nested():
                identifier = json_post['id']
                if identifier in existing_ids:
                    continue

                entities = json_post.get('geo_linked_entities', [])
                locations = [{
                    "lon": entity["location"]["lon"],
                    "lat": entity["location"]["lat"],
                    "name": entity["location"]["name"],
                    "boundingbox": None,
                    "osm_type": entity["location"]["osm_type"],
                    "osm_id": entity["location"]["osm_id"],
                    "mention": entity["mention"],
                    "status": entity.get("status", "ok"),
                } if (entity["location"] is not None and "osm_id" in entity["location"]) else {
                    "mention": entity["mention"],
                    "status": entity.get("status", "no_candidates"),
                } for entity in entities ]

                # Upsert polygon into the shared lookup table
                for entity in entities:
                    loc = entity.get("location")
                    if loc and loc.get("osm_id") and loc.get("osm_type") and loc.get("polygon"):
                        existing_poly = session.query(LocationPolygon).filter_by(
                            osm_id=str(loc["osm_id"]), osm_type=loc["osm_type"]
                        ).first()
                        if not existing_poly:
                            session.add(LocationPolygon(
                                osm_id=str(loc["osm_id"]),
                                osm_type=loc["osm_type"],
                                polygon=loc["polygon"],
                            ))

                # convert the time field into a datetime object
                timestamp = datetime.fromisoformat(json_post['timestamp'].replace('Z', '+00:00'))

                platform = json_post['platform']

                text_field_key = TEXT_FIELD.get(platform, 'text')
                text = json_post.get(text_field_key) or json_post.get('text', '')

                # special formatting for RSS feeds
                # i.e. instead of 'rss', save 'rss/ndr'
                if platform == 'rss' and json_post.get('feed'):
                    platform = f'rss/{json_post["feed"]}'

                raw_types = json_post.get('event_types', [])
                mapped_types = list({event_mapping.get(et, 'Sonstiges') for et in raw_types}) or ['Sonstiges']

                # create a new post object
                report = Report(
                    identifier=identifier,
                    text=text,
                    url=json_post['url'],
                    platform=platform,
                    timestamp=timestamp,
                    # .get with 'unknown' fallback: an unexpected relevance URI used
                    # to KeyError and abort the whole batch — better to keep the post
                    # with relevance 'unknown' than to lose it (and its successors).
                    relevance=relevance_mapping.get(json_post['relevance'], 'unknown'),
                    event_type=mapped_types[0],     # legacy column — keep populated
                    event_types=mapped_types,
                    processing_status=json_post.get('processing_status', 'ok'),
                    geo_recognition_status=json_post.get('geo_recognition_status', 'ok'),
                    locations=locations,
                    original_locations=locations,
                    author=json_post.get('author', ''),
                    seen=False,
                    author_flagged=False)

                # add the post to the session
                session.add(report)
        except Exception as e:
            print(f"Skipping unsaveable post {json_post.get('id', '?')}: {e}", flush=True)
            continue

        counter += 1

    # commit and close the session
    session.commit()
    session.close()

    return counter

def classify_post(json_post: dict) -> str:

    # TODO: connect to classifier when ready
    # for now, this just a random value

    # return a random value from this list
    class_list = ['other', 'storm', 'flood', 'rain']

    return random.choice(class_list)

def fetch_osm_polygon(osm_type: str, osm_id: int):
    """
    Fetch polygon geometry for a given OSM object from Overpass API.
    :param osm_type: 'relation', 'way', or 'node'
    :param osm_id: integer OSM ID
    :return: GeoJSON-like dict with polygon geometry, or None
    """
    query = f"""
    [out:json];
    {osm_type}({osm_id});
    (._;>;);
    out body;
    """
    url = "https://overpass-api.de/api/interpreter"
    response = requests.post(url, data={"data": query})
    if response.status_code != 200:
        print(f"Error fetching OSM data: {response.status_code}")
        return None

    data = response.json()
    nodes = {el["id"]: (el["lon"], el["lat"]) for el in data["elements"] if el["type"] == "node"}
    ways = [el for el in data["elements"] if el["type"] == "way"]

    lines = []
    for way in ways:
        try:
            coords = [nodes[nid] for nid in way["nodes"] if nid in nodes]
            if len(coords) >= 2:
                lines.append(coords)
        except Exception as e:
            continue

    safe_lines = []
    for line in lines:
        try:
            # Only convert if it's not already a LineString
            if isinstance(line, LineString):
                safe_lines.append(line)
            elif isinstance(line, list) and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in line):
                safe_lines.append(LineString(line))
            else:
                print(f"Skipping invalid line: {line}")
        except Exception as e:
            print(f"Line conversion failed: {line} -> {e}")

    # polygonize returns a generator; wrap in list
    geom_collection = GeometryCollection(polygonize(safe_lines))

    # Extract valid polygons
    polygons = [geom for geom in geom_collection.geoms if geom.geom_type == 'Polygon']

    if polygons:
        # We have polygons, return as GeoJSON polygons or multipolygons
        geojson_polygons = [mapping(p) for p in polygons]
        return {
            "type": "MultiPolygon" if len(geojson_polygons) > 1 else "Polygon",
            "coordinates": [p["coordinates"] for p in geojson_polygons]
        }
    else:
        # No polygons found, treat safe_lines as open paths and return LineStrings
        geojson_lines = []
        for line in safe_lines:
            if isinstance(line, LineString):
                geojson_lines.append(mapping(line))
            else:
                geojson_lines.append(mapping(LineString(line)))

        # If there's just one line, return a LineString, else MultiLineString
        if len(geojson_lines) == 1:
            return {
                "type": "LineString",
                "coordinates": geojson_lines[0]["coordinates"]
            }
        else:
            return {
                "type": "MultiLineString",
                "coordinates": [line["coordinates"] for line in geojson_lines]
            }


if __name__ == '__main__':

    import os as _os
    if _os.environ.get('DEMO_MODE') == '1':
        print('DEMO_MODE is active — server_reports will not fetch real posts.')
        import sys as _sys
        _sys.exit(0)

    # an initial sleep, because the api might not be ready yet
    print(f'Waiting for the API to be ready. Sleeping for {TIMEOUT_DELAY} seconds')
    #time.sleep(30)
    start_date = datetime.now(tz=timezone.utc)

    # Backfill: fetch the last 3 days in 30-minute windows with 5-minute overlap
    BACKFILL_WINDOW = timedelta(minutes=120)
    BACKFILL_OVERLAP = timedelta(minutes=5)
    backfill_start = start_date - timedelta(days=3)
    print(f'Backfilling posts from {backfill_start.strftime("%Y-%m-%d %H:%M:%S")} UTC')
    window_start = backfill_start
    while window_start < start_date:
        window_end = min(window_start + BACKFILL_WINDOW, start_date)
        print(f'Backfill window: {window_start.strftime("%H:%M")} → {window_end.strftime("%H:%M %Y-%m-%d")} UTC')
        try:
            posts = fetch_social_media_posts(window_start, search_until=window_end)
            save_posts(posts)
        except Exception as e:
            print(f'Backfill window failed, skipping: {e}')
        window_start += BACKFILL_WINDOW - BACKFILL_OVERLAP
        time.sleep(0.1)
    print('Backfill complete. Starting live polling.')

    print(
        f'Starting to fetch posts from {start_date.strftime("%Y-%m-%d %H:%M:%S")} UTC'
    )
    search_since = start_date - timedelta(minutes=SEARCH_LOOK_BACK)
    while True:
        try:
            posts = list(fetch_social_media_posts(search_since))
        except Exception as e:
            print(f"Error fetching posts, retrying in next cycle: {e}")
            posts = []
            time.sleep(10)

        for post in posts:
            for location in post["geo_linked_entities"]:
                if location["location"] is not None:
                    location["location"]["polygon"] = location["location"]["geojson"]

        saved_counter = save_posts(posts)

        # Advance search_since to just before the newest post we saw, so the
        # next poll only fetches genuinely new posts instead of the full lookback window.
        if posts:
            latest_ts = max(
                datetime.fromisoformat(p['timestamp'].replace('Z', '+00:00'))
                for p in posts
            )
            search_since = latest_ts - timedelta(seconds=30)
        else:
            search_since = datetime.now(tz=timezone.utc) - timedelta(minutes=2)

        time.sleep(REQUEST_DELAY)
