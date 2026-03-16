import json
import os
import requests
from datetime import datetime, timedelta, timezone
from tqdm import tqdm

# database imports
from sqlalchemy import text, func, inspect
from geoalchemy2 import WKTElement
from shapely.geometry import shape
from data.model import Base, TABLES, Feature, FeatureSet, Dataset, Collection, Layer, Style, Colormap, Report, UserReportState
from data.connect import autoconnect_db

# request imports
from data.req_hamburg import get_api_collections, get_items_endpoint, get_base_endpoint, request_items

# the accepted json types for the item endpoints
ACCEPTED_JSON_TYPES = ['application/json', 'application/geo+json']

def api_to_db(session, refresh=True, verbose=False):
    """
    Reloads all datasets from api_configs.json, requests their data and saves it into the database.
    This creates new database entries for Dataset, Collection, FeatureSet, Layer, Style and Colormap.
    If refresh is set to True, it will overwrite existing database entries for Feature.
    """

    # open api_config.json as json
    api_configs = json.load(open('api_config.json', 'r', encoding='utf-8'))
    dataset_configs = api_configs['datasets']

    # iterate over all api configs
    for dataset_config in tqdm(dataset_configs, disable=not verbose, leave=False):

        # get the dataset url and collection identifiers
        url = dataset_config['url']
        collection_identifiers = dataset_config['collections'].keys()

        # request the dataset from the API
        dataset_response = requests.get(url).json()

        # takes the name from the api_config.json if it exists
        # otherwise use the name from the API response
        dataset_name = dataset_config.get('name', dataset_response['title'])
        dataset_description = dataset_response['description']

        # create and save the dataset
        dataset = Dataset(
            name=dataset_name,
            description=dataset_description,
            url=url,
            collection_identifiers=collection_identifiers
        )

        session.add(dataset)

        # get all collections from the collections endpoint
        collections = get_api_collections(url)

        for collection in collections:

            collection_id = collection['id']

            if collection_id in collection_identifiers:

                # get the collection config from the api_config.json
                collection_config = dataset_config['collections'][collection_id]

                # if a layer is specified in the api_config.json, use it
                # otherwise use the dataset name
                layer_name = collection_config.get('layer', dataset_name)

                # get the layer from the database
                layer = session.query(Layer).filter(Layer.name == layer_name).first()

                # if the layer does not exist, create it
                if layer is None:
                    layer = Layer(
                        name=layer_name
                    )
                    session.add(layer)
                
                popup_properties = collection_config.get('popup_properties', {})
                collection_style = collection_config.get('style', {})
                collection_colormap = collection_config.get('colormap', None)

                colormap = None

                if collection_colormap:

                    colormap = Colormap(
                        property=collection_colormap['property'],
                        min_color=collection_colormap['min_color'],
                        max_color=collection_colormap['max_color'],
                        min_value=collection_colormap['min_value'],
                        max_value=collection_colormap['max_value']
                    )

                    session.add(colormap)

                # create a new style
                # set default values here
                style = Style(
                    name             = collection['title'],
                    popup_properties = popup_properties,
                    border_color     = collection_style.get('border_color', '#3388ff'),
                    area_color       = collection_style.get('area_color', '#2277ee'),
                    marker_icon      = collection_style.get('marker_icon', 'circle'),
                    marker_color     = collection_style.get('marker_color', 'black'),
                    line_weight      = collection_style.get('line_weight', 3),
                    stroke           = collection_style.get('stroke', True),
                    opacity          = collection_style.get('opacity', 1.0),
                    line_cap         = collection_style.get('line_cap', 'round'),
                    line_join        = collection_style.get('line_join', 'round'),
                    dash_array       = collection_style.get('dash_array', None),
                    dash_offset      = collection_style.get('dash_offset', None),
                    fill             = collection_style.get('fill', True),
                    fill_opacity     = collection_style.get('fill_opacity', 0.2),
                    fill_rule        = collection_style.get('fill_rule', 'evenodd'),
                    colormap         = colormap
                )

                session.add(style)

                # number of features in the collection
                entries = collection['itemCount']

                # the link to the items and collection
                url_items = get_items_endpoint(collection)
                url_collection = get_base_endpoint(collection)

                # create a Collection database object
                db_collection = Collection(
                    identifier=collection.get('id', 'collection_identifier'),
                    name=collection_config.get('name', collection.get('name', 'collection_name')),
                    entries=entries,
                    url_items=url_items,
                    url_collection=url_collection,
                    dataset=dataset,
                )

                session.add(db_collection)

                # create a FeatureSet for the collection
                feature_set = FeatureSet(
                    name=db_collection.name,
                    layer=layer,
                    style=style,
                    collection=db_collection
                )

                session.add(feature_set)

            session.commit()
        
        if refresh:
            refresh(session, verbose=verbose)


def refresh(session, verbose=False):
    """
    Gets all Datasets in the database, requests their features and saves them in the database.
    This overwrites existing database entries for Feature only.
    """

    # iterate through all Features, and delete those whose FeatureSet has a Collection
    # those are the Features that are accessible via API and get requested again
    # if we would not delete them, we would have duplicates
    features = session.query(Feature).all()

    for feature in features:

        # if the collection is not None, the FeatureSet is accessible via API
        if feature.feature_set.collection is not None:
            
            # this Feature will be requested again, so delete it
            session.delete(feature)

    # get all datasets
    feature_sets = session.query(FeatureSet).all()

    # iterate over all FeatureSets
    for feature_set in tqdm(feature_sets, disable=not verbose, leave=False):
        
        # iterate over all collections in the dataset
        collection = feature_set.collection

        # skip if the collection is None, meaning the FeatureSet is not accessible via API
        if collection is None:
            continue

        # request the items from the API
        items_response = request_items(collection)
    
        # skip if the request failed
        if items_response is None:
            continue
    
        # get all items from the items endpoint
        features = items_response['features']
    
        for feature in features:
    
            # transform the feature into a database object
            db_feature = feature_to_obj(feature)

            if db_feature is None:
                continue

            # set the feature set manually
            db_feature.feature_set = feature_set

            session.add(db_feature)
    
        session.commit()

def feature_to_obj(geojson_feature: dict):
    """
    Transforms a GeoJSON feature (as a dictionary) into a database entry.
    """

    if geojson_feature['geometry'] is None:
        return None

    # Convert GeoJSON geometry to a Shapely geometry
    shapely_geom = shape(geojson_feature['geometry'])

    # Use Shapely geometry with `geoalchemy2`
    geometry_type = shapely_geom.geom_type
    wkt_geometry = shapely_geom.wkt
    srid = 4326
    geometry_element = WKTElement(wkt_geometry, srid)

    # Get the properties of the feature
    properties = geojson_feature.get('properties', {})

    # get and convert the timestamp from the properties
    unix_timestamp = properties.get('timestamp', None)
    if unix_timestamp is not None:
        timestamp = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    else:
        timestamp = None

    # finally, create the feature
    feature = Feature(
        feature_set=None,   # must be set later manually, i.e. with feature.feature_set = feature_set_object
        properties=properties,
        timestamp=timestamp,
        geometry_type=geometry_type,
        geometry=geometry_element
    )

    return feature

def create_event_entries(session):
    """
    Creates custom layer and style database entries for the Events and Predictions.
    """

    # get all layers, styles and featuresets with the name 'Events' and 'Predictions'
    db_layer_events = session.query(Layer).filter(Layer.name == 'Events').first()
    db_style_events = session.query(Style).filter(Style.name == 'Events').first()
    db_feature_set_events = session.query(FeatureSet).filter(FeatureSet.name == 'Events').first()
    db_layer_predictions = session.query(Layer).filter(Layer.name == 'Predictions').first()
    db_style_predictions = session.query(Style).filter(Style.name == 'Predictions').first()
    db_feature_set_predictions = session.query(FeatureSet).filter(FeatureSet.name == 'Predictions').first()

    # special styles that get used when an event of prediction is selected
    db_style_events_selected = session.query(Style).filter(Style.name == 'Events Selected').first()
    db_style_predictions_selected = session.query(Style).filter(Style.name == 'Predictions Selected').first()

    # if any layers, styles or featuresets do not exist, create them
    if db_layer_events is None:
        db_layer_events = Layer(
            name='Events'
        )
        session.add(db_layer_events)
        session.commit()
    
    if db_layer_predictions is None:
        db_layer_predictions = Layer(
            name='Predictions'
        )
        session.add(db_layer_predictions)
        session.commit()
    
    if db_style_events is None:

        # default style for events
        db_style_events = Style(
            name             = 'Events',
            popup_properties = {'Type': 'event_type', 'Time': 'time', 'Timestamp': 'timestamp'},
            border_color     = '#8206e8',
            area_color       = '#9121ed',
            marker_icon      = 'circle',
            marker_color     = 'red',
            line_weight      = 2,
            stroke           = True,
            opacity          = 1.0,
            line_cap         = 'round',
            line_join        = 'round',
            dash_array       = None,
            dash_offset      = None,
            fill             = True,
            fill_opacity     = 0.3,
            fill_rule        = 'evenodd',
            colormap         = None
        )
        session.add(db_style_events)
        session.commit()
    
    if db_style_predictions is None:

        # default style for predictions
        db_style_predictions = Style(
            name             = 'Predictions',
            popup_properties = {'Type': 'event_type', 'Time': 'time', 'Timestamp': 'timestamp'},
            border_color     = '#3388ff',
            area_color       = '#2277ee',
            marker_icon      = 'circle',
            marker_color     = 'lightred',
            line_weight      = 1,
            stroke           = True,
            opacity          = 0.8,
            line_cap         = 'round',
            line_join        = 'round',
            dash_array       = None,
            dash_offset      = None,
            fill             = True,
            fill_opacity     = 0.2,
            fill_rule        = 'evenodd',
            colormap         = None
        )
        session.add(db_style_predictions)
        session.commit()
    
    if db_feature_set_events is None:
        db_feature_set = FeatureSet(
            name='Events',
            layer=db_layer_events,
            style=db_style_events,
            collection=None
        )
        session.add(db_feature_set)
        session.commit()
    
    if db_feature_set_predictions is None:
        db_feature_set = FeatureSet(
            name='Predictions',
            layer=db_layer_predictions,
            style=db_style_predictions,
            collection=None
        )
        session.add(db_feature_set)
        session.commit()
    
    if db_style_events_selected is None:
        # default style for when an event is selected
        db_style_events_selected = Style(
            name             = 'Events Selected',
            popup_properties = {'Type': 'event_type', 'Time': 'time', 'Timestamp': 'timestamp'},
            border_color     = '#ed3821',
            area_color       = '#ee4433',
            marker_icon      = 'circle',
            marker_color     = 'red',
            line_weight      = 3,
            stroke           = True,
            opacity          = 1.0,
            line_cap         = 'round',
            line_join        = 'round',
            dash_array       = None,
            dash_offset      = None,
            fill             = True,
            fill_opacity     = 0.4,
            fill_rule        = 'evenodd',
            colormap         = None
        )

        session.add(db_style_events_selected)
        session.commit()
    
    if db_style_predictions_selected is None:
        # default style for when a prediction is selected
        db_style_predictions_selected = Style(
            name             = 'Predictions Selected',
            popup_properties = {'Type': 'event_type', 'Time': 'time', 'Timestamp': 'timestamp'},
            border_color     = '#ed810e',
            area_color       = '#ed8a21',
            marker_icon      = 'circle',
            marker_color     = 'lightred',
            line_weight      = 2,
            stroke           = True,
            opacity          = 0.8,
            line_cap         = 'round',
            line_join        = 'round',
            dash_array       = None,
            dash_offset      = None,
            fill             = True,
            fill_opacity     = 0.3,
            fill_rule        = 'evenodd',
            colormap         = None
        )

        session.add(db_style_predictions_selected)
        session.commit()

def get_default_style():
    style = Style(
        name             = 'default',
        popup_properties = {},
        border_color     = '#3388ff',
        area_color       = '#2277ee',
        marker_icon      = 'circle',
        marker_color     = 'black',
        line_weight      = 3,
        stroke           = True,
        opacity          = 1.0,
        line_cap         = 'round',
        line_join        = 'round',
        dash_array       = None,
        dash_offset      = None,
        fill             = True,
        fill_opacity     = 0.2,
        fill_rule        = 'evenodd',
        colormap         = None
    )
    return style

def migrate_columns():
    """
    Adds new columns to existing tables if they don't exist yet.
    Safe to call on an already-initialized database – uses IF NOT EXISTS.
    """
    engine, session = autoconnect_db()
    migrations = [
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS original_locations JSON",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS author VARCHAR DEFAULT ''",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS seen BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS author_flagged BOOLEAN NOT NULL DEFAULT FALSE",
        """CREATE TABLE IF NOT EXISTS user_report_state (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    hide BOOLEAN NOT NULL DEFAULT FALSE,
    flag BOOLEAN NOT NULL DEFAULT FALSE,
    flag_author VARCHAR,
    locations JSON,
    first_seen_at TIMESTAMP,
    CONSTRAINT uq_user_report UNIQUE (username, report_id)
)""",
        "CREATE INDEX IF NOT EXISTS ix_urs_username ON user_report_state (username)",
        "ALTER TABLE user_report_state ADD COLUMN IF NOT EXISTS new BOOLEAN NOT NULL DEFAULT TRUE",
    ]
    for sql in migrations:
        try:
            session.execute(text(sql))
        except Exception as e:
            print(f"Migration skipped ({sql[:60]}...): {e}")
    session.commit()
    session.close()
    engine.dispose()


def build_if_uninitialized():
    """
    Check if the database is uninitialized and if it is, run `build()`.
    Also runs column migrations for already-initialized databases.
    Returns True if the database was uninitialized, else False.
    """

    # connect to the database
    engine, session = autoconnect_db()

    # check if the tables exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # check if all tables exist
    # cross check with the TABLES list from model.py
    missing_tables = []
    for table in TABLES:
        if table.__tablename__ not in existing_tables:
            missing_tables.append(table.__tablename__)

    # close the database connection
    session.close()
    engine.dispose()

    # if any tables are missing, run build()
    if len(missing_tables) > 0:

        print(f"Database is missing tables {missing_tables}")
        print("Running build()...")

        build(verbose=True)

        return True

    # Tables exist – apply any pending column migrations
    print("Database is initialized")
    migrate_columns()
    return False

    
# build the database and populate it with data
# needs to be run when installing the project for the first time, OR when changing the database structure (i.e. adding tables to model.py)
def build(verbose=False):
    """
    Drops all tables and rebuilds the database.
    1. Connects to the database
    2. Activate the postgis extension
    3. Drops all tables
    4. Creates new empty tables for all database objects from database.py
    5. Requests all datasets and collections from the API and saves them to the database (Updates tables Dataset, Collection, FeatureSet, Style, Colormap)
    6. Request all items from the collections, transform them into Features and save them to the database (Updates table Feature)
    7. Closes the connection to the database
    """

    if verbose: print("=========================")
    if verbose: print(" Rebuilding the database")
    if verbose: print("=========================")

    # 1. connect to the database
    if verbose: print("Connecting to the database... ", end='')
    engine, session = autoconnect_db()
    if verbose: print("Done!")

    # 2. activate postGIS if not already enabled
    if verbose: print("Activating extensions... ", end='')
    session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    session.commit()
    if verbose: print("Done!")

    # 3. force drop all tables
    if verbose: print("Dropping existing tables... ", end='')
    Base.metadata.drop_all(engine)
    if verbose: print("Done!")

    # 4. create the tables
    if verbose: print("Creating tables... ", end='')
    Base.metadata.create_all(engine)
    if verbose: print("Done!")

    # create special database entries for events
    # currently unused until the event prediction project is finished
    # if verbose: print("Preparing database entries for Event Propagation... ", end='')
    # create_event_entries(session)
    # if verbose: print("Done!")

    # 5. transform geojson files to database entries
    if verbose: print("Getting API Metadata... ")
    api_to_db(session, refresh=False, verbose=verbose)

    # get the number of Datasets and Collections
    dataset_count = session.query(Dataset).count()
    collection_count = session.query(Collection).count()
    if verbose: print(f"Saved {dataset_count} Datasets with {collection_count} Collections to the database")

    # 6. refresh all features
    if verbose: print("Refreshing Features... ")
    refresh(session, verbose=verbose)

    # get the number of Datasets and Collections
    feature_count = session.query(Feature).count()
    if verbose: print(f"Saved {feature_count} Features to the database")

    # 7. close the database connection
    session.close()
    engine.dispose()

    if verbose: print("=========================")
    if verbose: print("Database rebuild finished")
    if verbose: print("=========================")

# ---------------------------------------------------------------------------
# Demo mode
# ---------------------------------------------------------------------------

# (text, platform, event_type, relevance, author, [(loc_type, loc_name), ...])
# loc_type: 'georef' → resolved via Nominatim; 'mention' → mention only (no osm_id)
# Relevant reports placed at every 5th slot (indices 0,5,10,15,20,25,30,35,40,45)
# so that irrelevant posts appear continuously throughout all 5 minutes.
# Only ~10% of location-bearing posts use 'mention' (ungeoreferenced) — the rest are 'georef'.
DEMO_REPORTS = [
    # 0 – RELEVANT high
    (
        "WARNUNG: Hochwassergefahr an der Elbe – Pegelstand steigt rapide. "
        "Bewohner in Ufernähe sollen sich auf mögliche Überflutungen vorbereiten.",
        "rss/tagesschau", "Warnungen & Hinweise", "high", None,
        [("georef", "Elbe")],
    ),
    # 1 – irrelevant
    (
        "Gerade beim Bäcker – die Brötchen sind heute besonders gut. Das Leben geht weiter, Leute!",
        "mastodon", "Irrelevant", "none", "hh_blogger", [],
    ),
    # 2 – irrelevant  (one of two 'mention' placeholders kept, ~8% of located posts)
    (
        "Schaut euch die Alster an – absolut unwirkliche Stimmung heute Morgen. Hab das noch nie so gesehen.",
        "bluesky", "Irrelevant", "none", "weather_nerd_hh", [("mention", "Alster")],
    ),
    # 3 – irrelevant
    (
        "Jemand aus Blankenese hier? Gibt es in eurem Bereich Probleme mit dem Handynetz?",
        "reddit", "Irrelevant", "none", "hamburg_skeptic", [("georef", "Blankenese")],
    ),
    # 4 – irrelevant
    (
        "Hamburger Philharmoniker geben Solidaritätskonzert – Einnahmen gehen an Flutopfer.",
        "rss/ndr", "Sonstiges", "low", None, [],
    ),
    # 5 – RELEVANT high
    (
        "Evakuierung läuft! In Altona werden Bewohner tiefer gelegener Straßen "
        "aufgefordert, sofort ihre Häuser zu verlassen. Bitte meidet die Gegend.",
        "mastodon", "Evakuierungen & Umsiedlungen", "high", "hvb_altona",
        [("georef", "Altona")],
    ),
    # 6 – irrelevant
    (
        "Hat jemand Infos, ob der Flughafen noch normal betrieben wird? Muss morgen früh fliegen.",
        "mastodon", "Irrelevant", "none", "just_curious_hh", [],
    ),
    # 7 – irrelevant
    (
        "Fotos aus der HafenCity – die Reflexionen im Wasser sind beeindruckend. Link in Bio.",
        "bluesky", "Irrelevant", "none", "hh_fotograf", [("georef", "HafenCity")],
    ),
    # 8 – irrelevant
    (
        "Hat jemand aktuelle Infos zum Pegelstand der Elbe? Ich finde nichts Verlässliches.",
        "reddit", "Irrelevant", "low", "concerned_citizen", [("georef", "Elbe")],
    ),
    # 9 – irrelevant
    (
        "Bahn fährt mal wieder nicht. Klassiker.",
        "mastodon", "Irrelevant", "none", "daily_commuter", [],
    ),
    # 10 – RELEVANT high
    (
        "Feuerwehr meldet mehrere Verletzte nach Sturm: Drei Personen wurden ins UKE "
        "eingeliefert, eine Person befindet sich in kritischem Zustand.",
        "rss/tagesschau", "Verletzte & Tote", "high", None,
        [],
    ),
    # 11 – irrelevant
    (
        "Kochabend abgesagt wegen der Lage. Bleibt alle safe!",
        "bluesky", "Irrelevant", "none", "cooking_hh", [],
    ),
    # 12 – irrelevant
    (
        "Komme gerade aus Rahlstedt, da ist es super ruhig. Keine Ahnung was der Hype soll.",
        "reddit", "Irrelevant", "none", "lost_tourist", [("georef", "Rahlstedt")],
    ),
    # 13 – irrelevant
    (
        "Bundeskanzler äußert sich zur Lage in Hamburg und sichert Unterstützung zu.",
        "rss/tagesschau", "Sonstiges", "low", None, [],
    ),
    # 14 – irrelevant
    (
        "Meine Wohnung in Altona ist zum Glück nicht betroffen. Atme auf.",
        "mastodon", "Irrelevant", "none", "landlord_hh", [("georef", "Altona")],
    ),
    # 15 – RELEVANT high
    (
        "THW und Feuerwehr im Großeinsatz in der Innenstadt: Mehrere Pumpen im Betrieb, "
        "Sandsäcke werden verteilt. Bevölkerung aufgefordert, Ruhe zu bewahren.",
        "bluesky", "Einsatzmaßnahmen", "high", "rescue_hh",
        [("georef", "Innenstadt")],
    ),
    # 16 – irrelevant
    (
        "Vorlesungen morgen abgesagt. Wenigstens was Positives.",
        "bluesky", "Irrelevant", "none", "hh_influencer", [],
    ),
    # 17 – irrelevant
    (
        "Wer wettet, wann der Pegel wieder fällt? Ich tippe auf Donnerstag.",
        "reddit", "Irrelevant", "none", "gambler_hh", [],
    ),
    # 18 – irrelevant
    (
        "Meine Katze in Bergedorf versteht nicht, warum ich nicht rausgehe. Sie schaut mich so komisch an.",
        "mastodon", "Irrelevant", "none", "cat_mama_hh", [("georef", "Bergedorf")],
    ),
    # 19 – irrelevant
    (
        "Gerücht: S-Bahn Linie 31 soll komplett eingestellt werden. Kann das jemand bestätigen?",
        "bluesky", "Infrastruktur-Schäden", "low", "s_bahn_beobachter", [],
    ),
    # 20 – RELEVANT high
    (
        "VERMISST: 72-jährige Frau aus HafenCity seit gestern Abend nicht mehr gesehen. "
        "Zuletzt in der Nähe des Magdeburger Hafens gesehen. Bitte Polizei informieren.",
        "mastodon", "Vermisste & Gefundene", "high", "polizei_hh_info",
        [("georef", "HafenCity")],
    ),
    # 21 – irrelevant
    (
        "Hat jemand eine Zahl, wie viele Leute evakuiert wurden? Die Meldungen variieren stark.",
        "reddit", "Menschen betroffen", "low", "reddit_hh_aktuell", [("georef", "Wilhelmsburg")],
    ),
    # 22 – irrelevant
    (
        "Wie immer viel Lärm und am Ende passiert eh nichts Schlimmes. Aufgebauscht.",
        "mastodon", "Irrelevant", "none", "hamburg_skeptic", [],
    ),
    # 23 – irrelevant
    (
        "Erinnert mich an 2013 in Altona. Das haben wir damals auch irgendwie hingekriegt.",
        "bluesky", "Irrelevant", "none", "nostalgia_hh", [("georef", "Altona")],
    ),
    # 24 – irrelevant
    (
        "Hört auf eure Eltern und verlasst keine sicheren Gebiete ohne triftigen Grund. Bleibt daheim.",
        "reddit", "Warnungen & Hinweise", "low", "safety_first_hh", [],
    ),
    # 25 – RELEVANT medium
    (
        "Über 200 Familien in Wilhelmsburg betroffen. Notunterkünfte in der "
        "Wilhelmsburger Schule eingerichtet. Freiwillige werden dringend gesucht.",
        "reddit", "Menschen betroffen", "medium", "wilhelmsburg_aktuell",
        [("georef", "Wilhelmsburg")],
    ),
    # 26 – irrelevant
    (
        "Hamburger Sportverein sagt Trainingseinheit wegen Unwetter ab.",
        "rss/ndr", "Irrelevant", "none", None, [],
    ),
    # 27 – irrelevant
    (
        "Meine Reichweite explodiert gerade, weil ich über die Lage poste. Sollte ich das ausnutzen?",
        "mastodon", "Irrelevant", "none", "hh_influencer", [],
    ),
    # 28 – irrelevant
    (
        "Ich bin nicht aus Hamburg – was genau ist passiert? Ich verstehe die Meldungen nicht.",
        "bluesky", "Irrelevant", "none", "confused_outsider", [],
    ),
    # 29 – irrelevant
    (
        "Gassi gehen in Finkenwerder gerade nicht möglich. Mein Hund flippt aus.",
        "reddit", "Irrelevant", "none", "dog_owner_hh", [("georef", "Finkenwerder")],
    ),
    # 30 – RELEVANT medium
    (
        "Erhebliche Infrastrukturschäden in der HafenCity: Unterführung gesperrt, "
        "Bahnlinie S3 teilweise eingestellt, mehrere Straßen überflutet.",
        "bluesky", "Infrastruktur-Schäden", "medium", "hh_verkehr",
        [("georef", "HafenCity")],
    ),
    # 31 – irrelevant  (second 'mention' placeholder — ~8% of located posts)
    (
        "Sehe gerade 3 Feuerwehrautos in Richtung Harburg fahren. Hoffentlich nichts Ernstes.",
        "mastodon", "Einsatzmaßnahmen", "low", "feuerwehr_fan", [("mention", "Harburg")],
    ),
    # 32 – irrelevant
    (
        "Es ist 3 Uhr nachts und ich scrolle durch Katastrophenmeldungen. Alles okay bei mir.",
        "bluesky", "Irrelevant", "none", "night_owl_hh", [],
    ),
    # 33 – irrelevant
    (
        "Mein Bruder wohnt in Blankenese und sagt es ist alles okay bei ihm. Nur viel Wind.",
        "reddit", "Irrelevant", "low", "weather_watcher", [("georef", "Blankenese")],
    ),
    # 34 – irrelevant
    (
        "BREAKING: Hamburger Senat plant trotz Flut keine Notfallsitzung am Wochenende. Prioritäten.",
        "mastodon", "Irrelevant", "none", "satirist_hh", [],
    ),
    # 35 – RELEVANT medium
    (
        "Dringend benötigt in Harburg: Trinkwasser, Decken und Hygieneartikel. "
        "Sachspenden bitte an das DRK-Lager bringen.",
        "mastodon", "Bedarfe & Anfragen", "medium", "drk_harburg",
        [("georef", "Harburg")],
    ),
    # 36 – irrelevant
    (
        "Stromausfall seit 2 Stunden. Tippe das auf Akku. Tschüss Internet scheinbar.",
        "bluesky", "Irrelevant", "none", "bored_at_home", [],
    ),
    # 37 – irrelevant
    (
        "Solidarität aus ganz Deutschland: Spendenaktion für Hamburger Flutopfer sammelt Millionen.",
        "rss/tagesschau", "Mitgefühl & Unterstützung", "low", None, [],
    ),
    # 38 – irrelevant
    (
        "Berichte aus der HafenCity sind widersprüchlich. Bitte nur offizielle Quellen vertrauen.",
        "mastodon", "Irrelevant", "none", "local_journalist", [("georef", "HafenCity")],
    ),
    # 39 – irrelevant
    (
        "Mein Hotel ist zum Glück sicher. Kann aber Hamburg wegen Zugausfällen nicht verlassen.",
        "bluesky", "Irrelevant", "none", "tourist_stranded", [],
    ),
    # 40 – RELEVANT medium
    (
        "Rettungskräfte in Harburg seit 18 Stunden ununterbrochen aktiv. "
        "Unterstützung aus Niedersachsen angefordert.",
        "rss/tagesschau", "Einsatzmaßnahmen", "medium", None,
        [("georef", "Harburg")],
    ),
    # 41 – irrelevant
    (
        "Typisch Hamburg-Hysterie. Ich erinnere an 2020 als auch alle Panik hatten und nichts passierte.",
        "reddit", "Irrelevant", "none", "hamburg_skeptic", [],
    ),
    # 42 – irrelevant
    (
        "Homeoffice in der Innenstadt – alles ruhig hier im Büro. Die Lage draußen sieht schlimmer aus als sie ist.",
        "mastodon", "Irrelevant", "none", "tech_worker", [("georef", "Innenstadt")],
    ),
    # 43 – irrelevant
    (
        "Gibt es irgendwo eine Liste, wo man sich als Freiwilliger anmelden kann? Finde nichts Offizielles.",
        "bluesky", "Bedarfe & Anfragen", "low", "volunteer_seeker", [("georef", "Altona")],
    ),
    # 44 – irrelevant
    (
        "Bin erst seit 2 Monaten in Hamburg. Ist das hier normal? Alle so aufgeregt.",
        "reddit", "Irrelevant", "none", "hh_newbie", [],
    ),
    # 45 – RELEVANT medium
    (
        "Pegelwarnung für Finkenwerder: Deich wird überwacht, Anwohner sollen "
        "wachsam sein. Stand: 6,2 m ü. NN.",
        "reddit", "Warnungen & Hinweise", "medium", "finkenwerder_lokal",
        [("georef", "Finkenwerder")],
    ),
    # 46 – irrelevant
    (
        "In solchen Momenten wird einem bewusst, wie fragil unsere Infrastruktur eigentlich ist.",
        "mastodon", "Irrelevant", "none", "philosophy_buff", [],
    ),
    # 47 – irrelevant
    (
        "Schon wieder Hamburg unter Wasser. Hab schon ein Wasserstand-Meme vorbereitet, falls jemand will.",
        "bluesky", "Irrelevant", "none", "hh_influencer", [],
    ),
    # 48 – irrelevant
    (
        "Stadtpark und Alster-Promenaden gesperrt bis auf weiteres wegen Überflutungsgefahr.",
        "rss/ndr", "Sonstiges", "low", None, [("georef", "Alster")],
    ),
    # 49 – irrelevant
    (
        "In Rahlstedt ist die Welt noch in Ordnung. Gute Nacht, Hamburg. Bleibt stark!",
        "mastodon", "Irrelevant", "none", "last_poster_hh", [("georef", "Rahlstedt")],
    ),
]


def seed_demo_data(session):
    """
    Delete all existing reports and insert staggered demo reports from demo_data.json.
    The first report gets timestamp=now, the last gets timestamp=now+5min.

    Run `python src/prepare_demo.py` once to generate demo_data.json before using this.
    """
    demo_json = os.path.join(os.path.dirname(__file__), 'demo_data.json')
    if not os.path.exists(demo_json):
        raise FileNotFoundError(
            f"Demo data file not found: {demo_json}\n"
            "Run `python src/prepare_demo.py` first to pre-resolve OSM locations."
        )

    with open(demo_json, 'r', encoding='utf-8') as f:
        records = json.load(f)

    session.query(UserReportState).delete(synchronize_session=False)
    session.query(Report).delete(synchronize_session=False)
    session.commit()

    now = datetime.utcnow()
    n = len(records)
    step = 300.0 / max(n - 1, 1)  # spread over 5 minutes

    for i, rd in enumerate(records):
        ts = now + timedelta(seconds=i * step)
        locs = rd.get('locations', [])
        session.add(Report(
            identifier=rd['identifier'],
            text=rd['text'],
            url=rd['url'],
            platform=rd['platform'],
            timestamp=ts,
            event_type=rd['event_type'],
            relevance=rd['relevance'],
            locations=locs,
            original_locations=locs,
            author=rd.get('author', ''),
            seen=False,
            author_flagged=False,
        ))

    session.commit()
    print(f"Demo: seeded {n} reports, first at now, last at now+5 min")


# if this file is run directly, rebuild the database
if __name__ == '__main__':
    build(verbose=True)