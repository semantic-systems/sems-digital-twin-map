import json
import requests
from tqdm import tqdm

# database imports
from sqlalchemy import text, func
from geoalchemy2 import WKTElement
from shapely.geometry import shape
from data.model import Base, Feature, FeatureSet, Dataset, Collection, Layer, Style, Colormap
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
    for dataset_config in tqdm(dataset_configs, disable=not verbose):

        # split the line at the comma
        url = dataset_config['url']
        collection_identifiers = dataset_config['collections'].keys()

        # request the dataset from the API
        dataset_response = requests.get(url).json()

        # takes the name from the api_config.json if it exists
        # otherwise use the name from the API response
        dataset_name = dataset_config.get('name', dataset_response['title'])
        dataset_description = dataset_response['description']

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
    Gets all Datasets in the database, requests their data and saves it into the database.
    This overwrites existing database entries for Feature only.
    """

    # drop all existing features
    session.query(Feature).delete()

    # get all datasets
    feature_sets = session.query(FeatureSet).all()

    # iterate over all FeatureSets
    for feature_set in tqdm(feature_sets, disable=not verbose):
        
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

    # finally, create the feature
    feature = Feature(
        feature_set=None,   # None for now, must be set later manually
        properties=properties,
        geometry_type=geometry_type,
        geometry=geometry_element
    )

    return feature

def create_event_entries(session):
    """
    Creates a layer and style database entry for the Events and Predictions.
    """

    # get all layers and styles with the name 'Events'
    db_layer = session.query(Layer).filter(Layer.name == 'Events').first()
    db_style = session.query(Style).filter(Style.name == 'Events').first()

    # if the layer or style do not exist, create them
    if db_layer is None:
        db_layer = Layer(
            name='Events'
        )
        session.add(db_layer)
        session.commit()
    
    if db_style is None:
        # style events and predictions here
        # TODO: create a json entry that holds these values
        db_style_events = Style(
            name             = 'Events',
            popup_properties = {'Type': 'event_type', 'Time': 'time', 'Timestamp': 'timestamp'},
            border_color     = '#ee4433',
            area_color       = '#ee2211',
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
            fill_opacity     = 0.3,
            fill_rule        = 'evenodd',
            colormap         = None
        )
        db_style_predictions = Style(
            name             = 'Predictions',
            popup_properties = {'Type': 'event_type', 'Time': 'time', 'Timestamp': 'timestamp'},
            border_color     = '#3388ff',
            area_color       = '#2277ee',
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
            fill_opacity     = 0.2,
            fill_rule        = 'evenodd',
            colormap         = None
        )
        session.add(db_style_events)
        session.add(db_style_predictions)
        session.commit()
    
# build the database and populate it with data
# only needs to be run once
# but you should still refresh once in a while with database.refresh()
def build(verbose=False):
    """
    Drops all tables and rebuilds the database.
    1. Connects to the database
    2. Activates postgis with `CREATE EXTENSION IF NOT EXISTS postgis`
    3. Drops all tables
    4. Creates new empty tables for all database objects from database.py
    5. Requests all datasets and collections from the API and saves them to the database (Updates tables Dataset, Collection, FeatureSet, Style, Colormap)
    6. Request all items from the collections, transform them into Features and save them to the database (Updates table Feature)
    7. Closes the connection to the database
    """

    if verbose: print("=========================")
    if verbose: print(" Rebuilding the database")
    if verbose: print("=========================")

    # connect to the database
    if verbose: print("Connecting to the database... ", end='')
    engine, session = autoconnect_db()
    if verbose: print("Done!")

    # activate postGIS if its not already enabled
    if verbose: print("Activating postgis... ", end='')
    session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    if verbose: print("Done!")

    # force drop all tables
    if verbose: print("Dropping existing tables... ", end='')
    Base.metadata.drop_all(engine)
    if verbose: print("Done!")

    # create the tables
    if verbose: print("Creating tables... ", end='')
    Base.metadata.create_all(engine)
    if verbose: print("Done!")

    # create special database entries for events
    if verbose: print("Creating layer and style database entries for Event Propagation... ", end='')
    create_event_entries(session)
    if verbose: print("Done!")

    # transform geojson files to database entries
    if verbose: print("Getting API Metadata... ")
    api_to_db(session, refresh=False, verbose=verbose)

    # get the number of Datasets and Collections
    dataset_count = session.query(Dataset).count()
    collection_count = session.query(Collection).count()
    if verbose: print(f"Saved {dataset_count} Datasets with {collection_count} Collections to the database")

    # reload all datasets
    if verbose: print("Refreshing Features... ")
    refresh(session, verbose=verbose)

    # get the number of Datasets and Collections
    feature_count = session.query(Feature).count()
    if verbose: print(f"Saved {feature_count} Features to the database")

    # close the database connection
    session.close()
    engine.dispose()

    if verbose: print("=========================")
    if verbose: print("Database rebuild finished")
    if verbose: print("=========================")

# if this file is run directly, rebuild the database
if __name__ == '__main__':
    build(verbose=True)