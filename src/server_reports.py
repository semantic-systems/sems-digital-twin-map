import os
from collections import defaultdict

import requests
import time
from datetime import datetime, timedelta

from shapely import polygonize, GeometryCollection, LineString
from shapely.geometry import mapping
from SPARQLWrapper import SPARQLWrapper
from data.connect import autoconnect_db
from data.model import Report

import random   # can be removed later


SPARQL_ENDPOINT = os.getenv('SPARQL_ENDPOINT', '')
if not SPARQL_ENDPOINT:
    raise ValueError("SPARQL_ENDPOINT environment variable is not set.")

# how long to wait between requests (in seconds)
REQUEST_DELAY = 60 * 60 * 6    # 6 hours

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
SEARCH_LOOK_BACK = 10    # how many minutes to look back

sparql = SPARQLWrapper(SPARQL_ENDPOINT)


def fetch_social_media_posts(search_since: datetime):
    """Fetch posts from RescueMate KG."""

    search_since_str = search_since.isoformat()

    query = f"""
    PREFIX sm: <http://social_media_data.com/>
        SELECT * {{
        ?post a sm:Post ;
        ?post sm:text ?text ;
        ?post sm:created_at ?date ;
        ?post sm:predicted_category ?category ;
        ?post sm:platform ?platform ;
        ?post sm:mentioned_location ?location_mention ;
        ?post sm:url ?url .
        ?location_mention sm:location ?location ;
        ?location sm:osm_type ?osm_type ;
        ?location sm:osm_id ?osm_id ;
        ?location sm:latitude ?lat ;
        ?location sm:longitude ?lon ;
        ?location sm:name ?name ;
        ?location sm:display_name ?display_name ;
        ?location_mention sm:mention ?mention .
        
        FILTER (?date > "{search_since_str}"^^xsd:dateTime)
        }}
    """

    sparql.setQuery(query)
    sparql.setReturnFormat('json')
    sparql.setMethod('POST')
    sparql.addCustomHttpHeader('User-Agent', USER_AGENT)
    try:
        results = sparql.query().convert()
    except Exception as e:
        print(f"Error fetching data from SPARQL endpoint: {e}")
        return []
    if VERBOSE:
        print(f"Fetched {len(results['results']['bindings'])} posts from SPARQL endpoint", flush=True)
    posts = {}
    for result in results['results']['bindings']:
        post_id = result['post']['value'].split('/')[-1]

        if post_id not in posts:
            posts[post_id] = {
                'id': result['post']['value'].split('/')[-1],
                'text': result['text']['value'],
                'timestamp': result['date']['value'],
                'platform': result['platform']['value'].split('/')[-1],
                'url': result['url']['value'],
                'event_type': result.get('category', {}).get('value', 'other'),
                'geo_linked_entities': [{
                    'mention': result['mention']['value'],
                    'location': {
                        'osm_type': result['osm_type']['value'],
                        'osm_id': int(result['osm_id']['value']),
                        'lat': float(result['lat']['value']),
                        'lon': float(result['lon']['value']),
                        'name': result['name']['value'],
                        'display_name': result['display_name']['value']
                    }
                }]}
        else:
            posts[post_id]['geo_linked_entities'].append(
                {
                    'mention': result['mention']['value'],
                    'location': {
                        'osm_type': result['osm_type']['value'],
                        'osm_id': int(result['osm_id']['value']),
                        'lat': float(result['lat']['value']),
                        'lon': float(result['lon']['value']),
                        'name': result['name']['value'],
                        'display_name': result['display_name']['value']
                    }
                }
            )

    return list(posts.values())






def save_posts(posts: list):
    """Save the posts to the database"""

    engine, session = autoconnect_db()

    # count how many posts were saved
    counter = 0

    for json_post in posts:

        # get the post identifier
        # this is the id the respective platform uses to identify the post
        identifier = json_post['id']

        # check if the post already exists
        existing_post = session.query(Report).filter(Report.identifier == identifier).first()

        # skip if the post already exists
        if existing_post:
            continue

        # convert the time field into a datetime object
        timestamp = datetime.fromisoformat(json_post['timestamp'])

        platform = json_post['platform']

        text_field_key = TEXT_FIELD[platform]
        text = json_post[text_field_key]

        # special formatting for RSS feeds
        # i.e. instead of 'rss', save 'rss/ndr'
        if platform == 'rss':
            platform = f'rss/{json_post["feed"]}'

        entities = json_post.get('geo_linked_entities', [])
        locations = [{
            "lon": entity["location"]["lon"],
            "lat": entity["location"]["lat"],
            "name": entity["location"]["name"],
            "display_name": entity["location"]["display_name"],
            "boundingbox": None,
            "osm_type": entity["location"]["osm_type"],
            "osm_id": entity["location"]["osm_id"],
            "polygon": entity["location"]["polygon"],
            "mention": entity["mention"]
        } for entity in entities if isinstance(entity.get("location"), dict)]


        # create a new post object
        report = Report(
            identifier=identifier,
            text=text,
            url=json_post['url'],
            platform=platform,
            timestamp=timestamp,
            event_type=json_post['event_type'],
            locations=locations)

        # add the post to the session
        session.add(report)

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

    # an initial sleep, because the api might not be ready yet
    print(f'Waiting for the API to be ready. Sleeping for {TIMEOUT_DELAY} seconds')
    time.sleep(30)

    search_since = datetime.now() - timedelta(minutes=SEARCH_LOOK_BACK)
    while True:
        new_search_since = datetime.now()
        posts = fetch_social_media_posts(search_since)
        search_since = new_search_since

        for post in posts:
            for location in post["geo_linked_entities"]:
                if location["location"] is not None:
                    osm_id = location["location"]["osm_id"]
                    osm_type = location["location"]["osm_type"]
                    polygon = fetch_osm_polygon(osm_type, osm_id)
                    location["location"]["polygon"] = polygon

        saved_counter = save_posts(posts)
        # if VERBOSE: print(f'Saved {saved_counter} posts', flush=True)
        #
        # if VERBOSE: print(f'Done! Waiting for {REQUEST_DELAY} seconds', flush=True)
        time.sleep(REQUEST_DELAY)