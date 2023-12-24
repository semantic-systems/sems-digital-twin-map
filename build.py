import os
import json
import requests
from tqdm import tqdm

# database imports
from sqlalchemy import text, func
from geoalchemy2 import WKTElement
from shapely.geometry import shape
from database import Base, Feature, Dataset, Collection, Layer, Style, Colormap, connect_db

# request imports
from req import get_api_collections, get_items_endpoint, request_items

# the accepted json types for the items endpoint
ACCEPTED_JSON_TYPES = ['application/json', 'application/geo+json']

def api_to_db(session, refresh=True, verbose=False):
    """
    Reloads all datasets from api_configs.json, requests their data and saves it into the database.
    This creates new database entries for Dataset, Collection, Layer and Style.
    If refresh is set to True, it will overwrite existing database entries for Feature.
    """

    # open api_config.json as json
    api_configs = json.load(open('api_config.json', 'r', encoding='utf-8'))
    dataset_configs = api_configs['datasets']

    # iterate over all api configs
    for dataset_config in tqdm(dataset_configs):

        # split the line at the comma
        url = dataset_config['url']
        collection_identifiers = dataset_config['collections'].keys()

        # request the dataset from the API
        dataset_response = requests.get(url).json()

        # takes the name from the api_config.json if it exists
        # otherwise use the title from the API response
        dataset_title = dataset_config.get('name', dataset_response['title'])
        dataset_description = dataset_response['description']

        dataset = Dataset(
            title=dataset_title,
            description=dataset_description,
            url=url,
            collection_identifiers=collection_identifiers
        )

        session.add(dataset)

        # create a new layer
        layer = Layer(
            name=dataset_title
        )

        session.add(layer)

        # get all collections from the collections endpoint
        collections = get_api_collections(url)

        for collection in collections:

            collection_id = collection['id']

            if collection_id in collection_identifiers:

                collection_config = dataset_config['collections'][collection_id]

                popup_properties = collection_config.get('popup_properties', {})
                collection_style = collection_config.get('style', {})

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
                )

                session.add(style)

                # number of features in the collection
                entries = collection['itemCount']

                # the link to the features/items
                items_link = get_items_endpoint(collection)

                # create a Collection database object
                db_collection = Collection(
                    identifier=collection.get('id', 'collection_identifier'),
                    title=collection_config.get('name', collection.get('title', 'collection_title')),
                    entries=entries,
                    url=items_link,

                    dataset=dataset,
                    layer=layer,
                    style=style
                )

                session.add(db_collection)

            session.commit()
        
        if refresh:
            refresh(session, verbose=verbose)

def refresh(session, verbose=False):
    """
    Gets all Datasets in the database, requests their data and saves it into the database.
    This overwrite existing database entries for Feature only.
    """

    # drop all existing features
    session.query(Feature).delete()

    # get all datasets
    datasets = session.query(Dataset).all()

    # iterate over all datasets
    for dataset in tqdm(datasets, disable=not verbose):

        collections = dataset.collections

        # iterate over all collections in the dataset
        for collection in collections:
                
            # request the items from the API
            items_response = request_items(collection)
    
            if items_response is None:
                continue
    
            # get all items from the items endpoint
            features = items_response['features']
    
            for feature in features:
    
                # skip features without a geometry
                if feature['geometry'] is None:
                    continue
    
                # Convert GeoJSON geometry to a Shapely geometry
                shapely_geom = shape(feature['geometry'])
    
                # Use Shapely geometry with `geoalchemy2`
                geometry_type = shapely_geom.geom_type
                wkt_geometry = shapely_geom.wkt
                srid = 4326
                geometry_element = WKTElement(wkt_geometry, srid)
    
                # create a new Feature database object
                db_feature = Feature(
                    geometry=geometry_element,
                    geometry_type=feature['geometry']['type'],
                    properties=feature['properties'],
    
                    collection=collection
                )
    
                session.add(db_feature)
    
            session.commit()

def feature_to_obj(geojson_feature):
    """
    Transforms a geojson feature into a database entry.
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

def style_to_obj(file_settings):
    """
    Transforms file specific settings from a settings.json into a Style database entry.
    """

    # check for a colormap
    colormap = None

    if 'colormap' in file_settings:
        colormap = Colormap(
            property=file_settings['colormap']['property'],
            min_color=file_settings['colormap']['colors'][0],
            max_color=file_settings['colormap']['colors'][1],
            min_value=file_settings['colormap']['vmin'],
            max_value=file_settings['colormap']['vmax']
        )
    
    style = Style(
        name=file_settings['name'],
        popup_properties=file_settings.get('popup_properties', {}),
        border_color=file_settings.get('border_color', 'blue'),
        area_color=file_settings.get('area_color', 'black'),
        icon_prefix=file_settings.get('icon-prefix', 'fa'),
        icon_name=file_settings.get('icon', 'circle'),
        icon_color=file_settings.get('icon_color', 'blue'),
        line_weight=file_settings.get('line_weight', 1.0),
        stroke=file_settings.get('stroke', True),
        opacity=file_settings.get('opacity', 1.0),
        line_cap=file_settings.get('line_cap', 'round'),
        line_join=file_settings.get('line_join', 'round'),
        dash_array=file_settings.get('dash_array', 1.0),
        dash_offset=file_settings.get('dash_offset', 1.0),
        fill=file_settings.get('fill', True),
        fill_opacity=file_settings.get('fill_opacity', 0.2),
        fill_rule=file_settings.get('fill_rule', 'evenodd'),
        colormap=colormap
    )

    return style, colormap

# build the database and populate it with data
# only needs to be run once
def build(verbose=False):

    if verbose: print("=========================")
    if verbose: print(" Rebuilding the database")
    if verbose: print("=========================")

    # connect to the database
    if verbose: print("Connecting to the database... ", end='')
    engine, session = connect_db()
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

    if verbose: print("=========================")
    if verbose: print("Database rebuild finished")
    if verbose: print("=========================")

# if this file is run directly, rebuild the database
if __name__ == '__main__':
    build(verbose=True)