import requests
import time
from datetime import datetime, timedelta

from shapely import polygonize, GeometryCollection, LineString
from shapely.geometry import mapping

from data.connect import autoconnect_db
from data.model import Report

import random   # can be removed later

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
SEARCH_LOOK_BACK = 7    # how many days to look back

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
            "boundingbox": entity["location"]["boundingbox"],
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

def search_posts() -> list:
    """Request posts from the previous week with the specified search parameters."""

    # get todays date
    today = datetime.now()

    # get the date from LOOK_BACK days ago
    since = today - timedelta(days=SEARCH_LOOK_BACK)

    # Define the request payload
    payload = {
        'query': SEARCH_QUERY,
        'since': since.strftime('%Y-%m-%d'),
        'until': today.strftime('%Y-%m-%d'),
        'limit': SEARCH_LIMIT,
        'subreddits': SEARCH_SUBREDDITS,
        'platforms': SEARCH_PLATFORMS,
        'mandatory_keywords': SEARCH_MANDATORY_KEYWORDS,
        'optional_keywords': SEARCH_OPTIONAL_KEYWORDS,
        'n_keywords': SEARCH_N_KEYWORDS,
        'w_regex': SEARCH_W_REGEX,
        'b_regex': SEARCH_B_REGEX
    }

    # Send a POST request
    response = requests.post(API_URL, json=payload)

    # Handle the response
    if response.status_code == 200:
        results = response.json()['results']

        return results
    else:
        print('Error:', response.status_code, response.text)

        return []

def classify_post(json_post: dict) -> str:

    # TODO: connect to classifier when ready
    # for now, this just a random value

    # return a random value from this list
    class_list = ['other', 'storm', 'flood', 'rain']

    return random.choice(class_list)

def classify_posts(posts):

    classified_posts = []

    for post in posts:

        # add the class to the post
        post['event_type'] = classify_post(post)
        classified_posts.append(post)
    
    return classified_posts


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

    while True:

        # if VERBOSE: print('Requesting... ', flush=True)
        # posts = search_posts()
        #
        # if VERBOSE: print('Classifying... ', flush=True)
        # posts = classify_posts(posts)
        #
        # if VERBOSE: print('Saving... ', flush=True)

        posts = [
                {
                    "id": "event001",
                    "text": "Eine verletzte Person wurde heute Mittag in der Nähe der Reeperbahn gemeldet. Rettungskräfte sind bereits vor Ort.",
                    "url": "https://mastodon.social/",
                    "platform": "mastodon",
                    "timestamp": "2025-05-22T12:15:00",
                    "event_type": "Verletzte oder Tote",
                    "geo_linked_entities":[{"mention":"Reeperbahn","location":{"place_id":25262600,"licence":"Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright","osm_type":"way","osm_id":40152904,"lat":"53.549892489110256","lon":"9.965817687449384","class":"highway","type":"secondary","place_rank":26,"importance":0.0533433333333333,"addresstype":"road","name":"Reeperbahn","display_name":"Reeperbahn, St. Pauli, Hamburg-Mitte, Hamburg, 20359, Deutschland","boundingbox":["53.5495582","53.5501073","9.9624143","9.9692292"]},"candidates":[["node",11471109383],["node",437328900],["way",136183490],["node",6611773066],["node",11367144307],["way",1197213768],["way",33848569],["way",26988299],["node",3376281840],["node",338228518],["node",12629385333],["way",40230851],["way",154188993],["node",288518841],["way",659767909],["node",3480061011],["way",43114783],["way",180152459],["way",40152904],["node",6611773067],["node",4417819561],["node",4794813789],["node",5580503412],["node",12308283870],["way",194677527],["node",300814266]]}]
                },
                {
                    "id": "event002",
                    "text": "Achtung in Altona: Polizei warnt vor starkem Wind und herabfallenden Ästen. Bitte meiden Sie Parks und Alleen!",
                    "url": "https://bsky.app",
                    "platform": "bluesky",
                    "timestamp": "2025-05-22T10:42:00",
                    "event_type": "Warnung und Hinweise",
                    "geo_linked_entities": [{"mention": "Altona", "location": {"place_id": 25190270,
                                                                               "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
                                                                               "osm_type": "relation", "osm_id": 30223,
                                                                               "lat": "53.5864667",
                                                                               "lon": "9.777670940463931",
                                                                               "class": "boundary",
                                                                               "type": "administrative",
                                                                               "place_rank": 18,
                                                                               "importance": 0.5570129015963227,
                                                                               "addresstype": "city_district",
                                                                               "name": "Altona",
                                                                               "display_name": "Altona, Hamburg, Deutschland",
                                                                               "boundingbox": ["53.5415333",
                                                                                               "53.6314046",
                                                                                               "9.7301155",
                                                                                               "9.9769646"]},
                                             "candidates": [["way", 690027488], ["node", 3183841635],
                                                            ["node", 290366234], ["relation", 77384],
                                                            ["node", 300809500], ["way", 293231621],
                                                            ["way", 1317570876], ["way", 42873615], ["way", 690707862],
                                                            ["node", 1686600807], ["way", 913897005],
                                                            ["node", 3357946758], ["node", 1686600810],
                                                            ["way", 746649521], ["node", 1686600813],
                                                            ["node", 300809530], ["way", 137352972],
                                                            ["relation", 30223], ["relation", 3132920],
                                                            ["node", 535951140], ["way", 30928631], ["way", 81163882],
                                                            ["way", 53060941], ["way", 328005284],
                                                            ["relation", 9426517], ["way", 1347026819],
                                                            ["way", 42873617], ["node", 6140117261], ["way", 662729032],
                                                            ["way", 690707861], ["node", 1686600809], ["way", 51398796],
                                                            ["way", 294928790], ["way", 55888020], ["node", 1686600812],
                                                            ["relation", 183607], ["node", 535951138],
                                                            ["node", 291151840], ["way", 52829066], ["way", 808524104],
                                                            ["way", 19337851], ["way", 1107177321],
                                                            ["relation", 1860037], ["way", 23656070],
                                                            ["node", 289785992], ["node", 1686600811],
                                                            ["way", 662729031], ["node", 1686600808],
                                                            ["node", 1686600814], ["way", 16507128]]},
                                            {"mention": "Polizei", "location": None,
                                             "candidates": [["way", 908226915], ["way", 140142170], ["way", 1144455228],
                                                            ["way", 204824528], ["way", 1101630545],
                                                            ["node", 12766310025], ["way", 60558734],
                                                            ["way", 1001533849], ["node", 618768705],
                                                            ["way", 118232462], ["node", 9458375080],
                                                            ["node", 1740678878], ["node", 265094247],
                                                            ["way", 96722612], ["way", 244318288], ["node", 660786951],
                                                            ["way", 122161148], ["way", 163806571], ["way", 369548382],
                                                            ["node", 2444268166], ["way", 1202485741],
                                                            ["relation", 301240], ["way", 321523681],
                                                            ["node", 9362783084], ["node", 2425477679],
                                                            ["way", 107702850], ["node", 3099383338],
                                                            ["way", 529628521], ["way", 189735001],
                                                            ["node", 4458071281], ["way", 143271973], ["way", 27218304],
                                                            ["way", 42776048], ["node", 299499080], ["way", 151895302],
                                                            ["relation", 7182365], ["node", 5842000400],
                                                            ["way", 228456150], ["way", 223139928],
                                                            ["node", 3095799987], ["way", 176771217],
                                                            ["node", 369972388], ["node", 10956916572],
                                                            ["node", 1521308952], ["way", 31256024], ["way", 149915387],
                                                            ["way", 164930289], ["way", 397967961], ["way", 220726828],
                                                            ["way", 724161614], ["way", 1368032804],
                                                            ["way", 1198190420], ["way", 113550292], ["way", 355251037],
                                                            ["way", 38706161], ["way", 107132912],
                                                            ["relation", 1867939], ["way", 618550552],
                                                            ["way", 151895301], ["node", 5472282062],
                                                            ["node", 4788310607], ["way", 249685555],
                                                            ["way", 1113027223], ["node", 2054699369],
                                                            ["node", 2335163469], ["node", 7549140086],
                                                            ["node", 12800606322], ["node", 271192197],
                                                            ["way", 1384508642], ["node", 4309809754],
                                                            ["way", 827891181], ["node", 1699192988],
                                                            ["node", 4696964278], ["way", 252744850]]},
                                            {"mention": "Parks", "location": None,
                                             "candidates": [["node", 5758884848], ["node", 5758884851],
                                                            ["way", 318978281], ["way", 1134466331], ["way", 148434465],
                                                            ["node", 5758884847], ["node", 5758884853],
                                                            ["node", 5758884850], ["way", 1160029003],
                                                            ["relation", 959663], ["node", 3710097290],
                                                            ["way", 495281528], ["node", 5758884849],
                                                            ["node", 5758884852], ["way", 868467703],
                                                            ["way", 627756293], ["way", 1136479355], ["way", 824554703],
                                                            ["relation", 16409845], ["way", 55568979],
                                                            ["relation", 1059437], ["way", 1127675732],
                                                            ["way", 1128467353]]},
                                            {"mention": "Alleen", "location": None,
                                             "candidates": [["way", 238538376], ["way", 25589655], ["way", 25981055]]}]
                },
                {
                    "id": "event003",
                    "text": "In Wilhelmsburg wird derzeit dringend nach Helfer:innen für die Essensverteilung gesucht. Jede Unterstützung zählt!",
                    "url": "https://mastodon.social/",
                    "platform": "mastodon",
                    "timestamp": "2025-05-22T13:30:00",
                    "event_type": "Spenden und Freiwilligenarbeit",
                    "geo_linked_entities": [{"mention": "Wilhelmsburg", "location": {"place_id": 25771995,
                                                                                     "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
                                                                                     "osm_type": "relation",
                                                                                     "osm_id": 2064796,
                                                                                     "lat": "53.4922921",
                                                                                     "lon": "9.9962167",
                                                                                     "class": "boundary",
                                                                                     "type": "administrative",
                                                                                     "place_rank": 20,
                                                                                     "importance": 0.4639836382488006,
                                                                                     "addresstype": "suburb",
                                                                                     "name": "Wilhelmsburg",
                                                                                     "display_name": "Wilhelmsburg, Hamburg-Mitte, Hamburg, Deutschland",
                                                                                     "address": {
                                                                                         "suburb": "Wilhelmsburg",
                                                                                         "borough": "Hamburg-Mitte",
                                                                                         "city": "Hamburg",
                                                                                         "ISO3166-2-lvl4": "DE-HH",
                                                                                         "country": "Deutschland",
                                                                                         "country_code": "de"},
                                                                                     "boundingbox": ["53.4538769",
                                                                                                     "53.5263913",
                                                                                                     "9.9388148",
                                                                                                     "10.0789512"]},
                                             "candidates": [["way", 150274978], ["way", 150268077], ["way", 28343281],
                                                            ["relation", 15953174], ["way", 547283361],
                                                            ["way", 963182778], ["node", 6872867178],
                                                            ["way", 669409986], ["way", 1026806763], ["way", 148331237],
                                                            ["way", 934947116], ["way", 25502942], ["way", 21727778],
                                                            ["node", 3372168828], ["relation", 8307015],
                                                            ["way", 448189652], ["relation", 16339854],
                                                            ["way", 148325873], ["way", 934947115], ["way", 295413215],
                                                            ["way", 398975312], ["way", 283494774], ["way", 1383256767],
                                                            ["way", 1026326899], ["way", 606450760],
                                                            ["node", 4183547846], ["way", 669400817], ["way", 26415791],
                                                            ["way", 449187971], ["way", 669400814],
                                                            ["node", 4452241822], ["node", 29361459],
                                                            ["relation", 2064796], ["way", 448189651],
                                                            ["relation", 1806126], ["way", 448189660],
                                                            ["way", 26415830], ["way", 52823306], ["way", 687537221],
                                                            ["way", 236685912], ["relation", 2240052],
                                                            ["way", 963182779], ["node", 345294491], ["way", 148331238],
                                                            ["node", 2463701772], ["way", 25528076], ["way", 158248747],
                                                            ["node", 5590251098], ["way", 448189650],
                                                            ["way", 448189653]]}]
                },
                {
                    "id": "event004",
                    "text": "Ein älterer Herr wird seit dem frühen Morgen im Bereich Eppendorf vermisst. Hinweise bitte an die Polizei Hamburg.",
                    "url": "https://bsky.app/",
                    "platform": "bluesky",
                    "timestamp": "2025-05-22T08:55:00",
                    "event_type": "Vermisste und gefundene Personen",
                    "geo_linked_entities": [{"mention": "Eppendorf", "location": {"place_id": 25432199,
                                                                                  "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
                                                                                  "osm_type": "relation",
                                                                                  "osm_id": 180540, "lat": "53.5903912",
                                                                                  "lon": "9.9868771",
                                                                                  "class": "boundary",
                                                                                  "type": "administrative",
                                                                                  "place_rank": 20,
                                                                                  "importance": 0.45567555359110823,
                                                                                  "addresstype": "suburb",
                                                                                  "name": "Eppendorf",
                                                                                  "display_name": "Eppendorf, Hamburg-Nord, Hamburg, Deutschland",
                                                                                  "boundingbox": ["53.5837132",
                                                                                                  "53.6028033",
                                                                                                  "9.9676637",
                                                                                                  "9.9974094"]},
                                             "candidates": [["way", 51096523], ["way", 81267301], ["node", 6985171368],
                                                            ["way", 137536863], ["way", 16231449], ["way", 584660174],
                                                            ["way", 244146625], ["way", 477652030],
                                                            ["relation", 2191572], ["way", 249304916],
                                                            ["way", 40128142], ["way", 59577083], ["way", 44735204],
                                                            ["way", 24846436], ["way", 1216003242], ["way", 59984790],
                                                            ["way", 244146624], ["relation", 1785810],
                                                            ["way", 973088658], ["way", 137536864], ["way", 5230060],
                                                            ["way", 143824741], ["way", 1029397527],
                                                            ["way", 1012302322], ["relation", 180540],
                                                            ["way", 26407357]]}]
                },
                {
                    "id": "event005",
                    "text": "Wasserversorgung in Hamm unterbrochen. Ursache ist ein Rohrbruch, der derzeit repariert wird. Bitte Vorräte nutzen.",
                    "url": "https://mastodon.social/",
                    "platform": "mastodon",
                    "timestamp": "2025-05-22T09:20:00",
                    "event_type": "Schäden an Infrastruktur und Versorgung",
                    "geo_linked_entities": [
                        {"mention":"Hamm","location":{"place_id":25682040,"licence":"Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright","osm_type":"relation","osm_id":1455385,"lat":"53.5534434","lon":"10.0512944","class":"boundary","type":"administrative","place_rank":20,"importance":0.4315858803929854,"addresstype":"suburb","name":"Hamm","display_name":"Hamm, Hamburg-Mitte, Hamburg, Deutschland","boundingbox":["53.5377541","53.5661079","10.0376053","10.0707064"]},"candidates":[["relation",453744],["relation",420585],["relation",62499],["relation",2063685],["relation",58587],["relation",420578],["node",2146217850],["relation",6656785],["relation",1248688],["relation",444949],["way",21808488],["relation",92378],["relation",1455385],["relation",1152685],["node",8399472051],["relation",420573],["relation",2399480],["relation",386414]]},
                        ]


                },
                {
                    "id": "event006",
                    "text": "Viele Menschen mussten heute Morgen aufgrund eines Brandes in einem Wohnhaus in Barmbek ihre Wohnungen verlassen.",
                    "url": "https://bsky.app/",
                    "platform": "bluesky",
                    "timestamp": "2025-05-22T07:45:00",
                    "event_type": "Evakuierungen und Vertriebenenhilfe",
                    "geo_linked_entities": [{
                          "mention": "Barmbek",
                          "location": {
                            "place_id": 25799842,
                            "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
                            "osm_type": "relation",
                            "osm_id": 284865,
                            "lat": "53.5988941",
                            "lon": "10.0480997",
                            "class": "boundary",
                            "type": "administrative",
                            "place_rank": 20,
                            "importance": 0.4309425633146216,
                            "addresstype": "suburb",
                            "name": "Barmbek-Nord",
                            "display_name": "Barmbek-Nord, Hamburg-Nord, Hamburg, Deutschland",
                            "boundingbox": ["53.5830363", "53.6083635", "10.0321363", "10.0700204"]
                          },
                          "candidates": [["node", 28842391], ["node", 1139671822], ["node", 6906144897], ["node", 3127971906],
                                         ["way", 244597018], ["way", 608715870], ["way", 185406925], ["way", 605693227],
                                         ["node", 551437190], ["way", 32533779], ["relation", 284863], ["way", 24062266],
                                         ["node", 551437186], ["way", 1082706509], ["node", 403879374], ["node", 33070435],
                                         ["node", 387843463], ["way", 22392733], ["way", 138104361], ["way", 185406921],
                                         ["node", 551437158], ["way", 636931154], ["way", 605693235], ["way", 464328202],
                                         ["way", 993750663], ["way", 789177080], ["relation", 284865], ["node", 3207078744],
                                         ["node", 3236186817], ["way", 36821531], ["way", 23618005], ["way", 185406923],
                                         ["way", 789177079]]
                        }]

                },
                {
                    "id": "event007",
                    "text": "In Harburg wird weiterhin dringend nach Decken und warmer Kleidung für Geflüchtete gesucht.",
                    "url": "https://mastodon.social/",
                    "platform": "mastodon",
                    "timestamp": "2025-05-22T11:00:00",
                    "event_type": "Hilfsgesuche oder Bedürfnisse",
                    "geo_linked_entities": [{
                          "mention": "Harburg",
                          "location": {
                            "place_id": 25114125,
                            "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
                            "osm_type": "relation",
                            "osm_id": 299467,
                            "lat": "53.4562216",
                            "lon": "9.9872112",
                            "class": "boundary",
                            "type": "administrative",
                            "place_rank": 20,
                            "importance": 0.488762755355946,
                            "addresstype": "suburb",
                            "name": "Harburg",
                            "display_name": "Harburg, Hamburg, 21073, Deutschland",
                            "boundingbox": ["53.4487475", "53.4753374", "9.9651077", "10.0067877"]
                          },
                          "candidates": [["way", 45340813], ["way", 957221480], ["relation", 28964], ["relation", 3133037],
                                         ["way", 274779267], ["way", 471639698], ["relation", 3132936], ["node", 374466887],
                                         ["node", 3707303127], ["way", 111428267], ["way", 580124831], ["way", 5836627],
                                         ["way", 34952150], ["way", 663152397], ["relation", 962455], ["relation", 299467],
                                         ["way", 26358505], ["way", 580124815], ["node", 3135336139], ["way", 288938027],
                                         ["way", 420065943], ["relation", 2736738], ["node", 92844592], ["way", 23732464],
                                         ["way", 23798869], ["way", 26439834], ["way", 43091536], ["way", 102713950],
                                         ["way", 124522006], ["node", 4725309875], ["relation", 2083497], ["way", 2898171],
                                         ["relation", 2659096], ["node", 265698348], ["relation", 8738090], ["way", 129023072]]
                        }]

                },
                {
                    "id": "event008",
                    "text": "Feuerwehr und THW sind derzeit im Einsatz in Bergedorf, um die beschädigten Stromleitungen zu sichern.",
                    "url": "https://bsky.app/",
                    "platform": "bluesky",
                    "timestamp": "2025-05-22T14:10:00",
                    "event_type": "Hilfs- und Rettungsmaßnahmen",
                    "geo_linked_entities": [{
                          "mention": "Bergedorf",
                          "location": {
                            "place_id": 24945368,
                            "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
                            "osm_type": "relation",
                            "osm_id": 28936,
                            "lat": "53.4858",
                            "lon": "10.2267",
                            "class": "boundary",
                            "type": "administrative",
                            "place_rank": 18,
                            "importance": 0.4620671634458037,
                            "addresstype": "suburb",
                            "name": "Bergedorf",
                            "display_name": "Bergedorf, Hamburg, Deutschland",
                            "boundingbox": ["53.3951118", "53.5264164", "10.0510373", "10.3252805"]
                          },
                          "candidates": [["relation", 5974561], ["way", 899477561], ["node", 6771290002], ["way", 230396455],
                                         ["node", 2630276107], ["node", 1837709327], ["node", 4010276891], ["relation", 404618],
                                         ["way", 1208750786], ["relation", 2097253], ["way", 154189076], ["way", 700678219],
                                         ["relation", 3132936], ["relation", 2193375], ["relation", 410134], ["way", 927212615],
                                         ["way", 24001823], ["relation", 28936]]
                        }]

                },
                {
                    "id": "event009",
                    "text": "Unsere Gedanken sind bei den Angehörigen der Betroffenen des gestrigen Unglücks in Winterhude. Viel Kraft in dieser Zeit.",
                    "url": "https://mastodon.social/",
                    "platform": "mastodon",
                    "timestamp": "2025-05-22T15:45:00",
                    "event_type": "Spenden und Freiwilligenarbeit",
                    "geo_linked_entities": [{
                      "mention": "Winterhude",
                      "location": {
                        "place_id": 25825863,
                        "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
                        "osm_type": "relation",
                        "osm_id": 284001,
                        "lat": "53.5963901",
                        "lon": "10.0038317",
                        "class": "boundary",
                        "type": "administrative",
                        "place_rank": 20,
                        "importance": 0.45087499617587307,
                        "addresstype": "suburb",
                        "name": "Winterhude",
                        "display_name": "Winterhude, Hamburg-Nord, Hamburg, Deutschland",
                        "boundingbox": ["53.5753290", "53.6100971", "9.9912541", "10.0370750"]
                      },
                      "candidates": [["way", 1204382191], ["way", 32808515], ["way", 60558734], ["way", 186153683],
                                     ["way", 132894517], ["way", 60558703], ["node", 10137633522], ["way", 54884829],
                                     ["way", 30415611], ["node", 11139550104], ["way", 162026563], ["way", 519104678],
                                     ["node", 2398686966], ["node", 327636263], ["way", 1196392767], ["node", 10154790262],
                                     ["way", 132260151], ["node", 332576439], ["node", 281923855], ["way", 1156157352],
                                     ["node", 1783925694], ["relation", 284001], ["way", 33957429], ["way", 3756548],
                                     ["way", 953955166], ["node", 4767729514], ["way", 4019141], ["node", 327578924],
                                     ["way", 33290203]]
                    }]

                },
                {
                    "id": "event011",
                    "text": "Heute findet in der Hafencity eine Demonstration zum Thema Stadtentwicklung statt. Verkehrsbehinderungen möglich.",
                    "url": "https://mastodon.social/",
                    "platform": "mastodon",
                    "timestamp": "2025-05-22T11:50:00",
                    "event_type": "Nicht-humanitäres Ereignis",
                    "geo_linked_entities": [{
                          "mention": "Hafencity",
                          "location": {
                            "place_id": 25813177,
                            "licence": "Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright",
                            "osm_type": "relation",
                            "osm_id": 28931,
                            "lat": "53.5429127",
                            "lon": "9.9958346",
                            "class": "boundary",
                            "type": "administrative",
                            "place_rank": 20,
                            "importance": 0.458793274077304,
                            "addresstype": "suburb",
                            "name": "HafenCity",
                            "display_name": "HafenCity, Hamburg-Mitte, Hamburg, 20457, Deutschland",
                            "boundingbox": ["53.5300578", "53.5469165", "9.9803816", "10.0315651"]
                          },
                          "candidates": [["node", 10934442772], ["node", 12752563279], ["way", 40012955], ["node", 6496495941],
                                         ["node", 1272392517], ["node", 6343310177], ["node", 401428545], ["way", 1031829718],
                                         ["node", 3898140535], ["node", 312586268], ["node", 3149418166], ["node", 3222181945],
                                         ["way", 464330442], ["way", 1319015029], ["way", 1375079894], ["node", 12205514915],
                                         ["node", 3738942416], ["node", 2306864722], ["way", 60689764], ["way", 381551526],
                                         ["node", 9922411694], ["node", 2306851008], ["node", 1549516900], ["node", 2956940308],
                                         ["node", 4458765493], ["way", 193661306], ["node", 3683385298], ["relation", 28931],
                                         ["node", 2435701660], ["node", 9981354117], ["way", 343691248], ["node", 9595339695]]
                        }]

                }
            ]

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