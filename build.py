import os
import json
import requests
from tqdm import tqdm

# database imports
from sqlalchemy import text, func
from geoalchemy2 import WKTElement
from shapely.geometry import shape
from database import Base, Feature, FeatureSet, Layer, Style, Dataset, Colormap, connect_db

# the accepted json types for the items endpoint
ACCEPTED_JSON_TYPES = ['application/json', 'application/geo+json']

def get_files(path='data') -> dict:
    """
    Returns a dictionary with the folder name as key and a list of files as value.
    """
    files = {}

    for root, dirs, filenames in os.walk(path):
        for f in filenames:

            # get the folder name after data\
            # i.e. emobility_json or hafengebiets_json
            folder = root.split(os.sep)[-1]

            # create a new list if the folder name is not in the dictionary
            if folder not in files:
                files[folder] = []
            
            # append the file name to the list
            files[folder].append(f)

    return files

def load_json(json_path, encoding='utf-8') -> dict:
    """
    Loads a json file and returns the json data as a dictionary.
    """
    json_data = {}
    with open(json_path, 'r', encoding=encoding) as settings_file:
        json_data = json.load(settings_file)
    return json_data

def get_api_collections(base_api):
    """
    Returns the collections endpoint from the API base URL
    For example:
    https://api.hamburg.de/datasets/v1/fahrradhaeuschen/
    returns
    https://api.hamburg.de/datasets/v1/fahrradhaeuschen/collections
    """
    # the header we send with our requests
    headers = {'Content-Type': 'application/json'}

    base_response = requests.get(base_api, headers=headers)

    collection_links = []

    # check if the request was successful
    if base_response.status_code == 200:

        base_json = base_response.json()
        base_links = base_json['links']

        # find the link with the rel 'data'
        for base_link in base_links:
            if base_link['rel'] == 'data':
                collections_api = base_link['href']

                collections_response = requests.get(collections_api, headers=headers)

                # check if the request was successful
                if collections_response.status_code == 200:
                    collections_json = collections_response.json()

                    return collections_json['collections']

def get_api_items(base_api):
    """
    Returns the items endpoint from the API base URL
    For example:
    https://api.hamburg.de/datasets/v1/fahrradhaeuschen/
    returns
    https://api.hamburg.de/datasets/v1/fahrradhaeuschen/collections/items?f=json

    :param base_api: the base URL of the API
    :return: the items endpoint or None if the items endpoint could not be found
    """

    # the header we send with our requests
    headers = {'Content-Type': 'application/json'}

    base_response = requests.get(base_api, headers=headers)

    item_links = []

    # check if the request was successful
    if base_response.status_code == 200:

        base_json = base_response.json()
        base_links = base_json['links']

        # find the link with the rel 'data'
        for base_link in base_links:
            if base_link['rel'] == 'data':
                collections_api = base_link['href']

                collections_response = requests.get(collections_api, headers=headers)

                # check if the request was successful
                if collections_response.status_code == 200:
                    collections_json = collections_response.json()

                    collections = collections_json['collections']

                    for collection in collections:
                        collection_links = collection['links']

                        # find the link with the rel 'items'
                        # and the type 'application/json' or 'application/geo+json'
                        for collection_link in collection_links:
                            if collection_link['rel'] == 'items' and collection_link['type'] in ACCEPTED_JSON_TYPES:
                                item_links.append(collection_link['href'])
    
    return item_links

def urls_to_db(session, verbose=False):
    """
    Gets all datasets from the API, requests their data and saves it into the database.
    """

    # read all urls from urls.txt
    with open('urls.txt', 'r') as urls_file:
        urls = urls_file.readlines()

    print(urls)

def datasets_to_db(session, verbose=False):
    """
    Gets all datasets in the database, requests their data and saves it into the database.
    """

    # get all datasets
    datasets = session.query(Dataset).all()

    for dataset in tqdm(datasets, disable=not verbose):
        dataset_to_db(dataset, session, verbose=verbose)

def dataset_to_db(dataset, session, verbose=False):
    """
    Takes a dataset, requests its data and transforms it into database entries.
    """

def files_to_db(files, session, base_path='data', verbose=False):
    """
    Transforms geojson files into database entries.
    Takes in files as a dictionary with the folder name as key and a list of files as value.
    These files are then processed and saved into the database.
    Each folder name should contain a settings.json file.
    """
    
    for category, file_list in tqdm(files.items(), disable=not verbose):

        # get the settings file for the category
        settings_path = os.path.join(base_path, category, 'settings.json')
        
        if os.path.exists(settings_path):
            category_settings = load_json(settings_path)

            layer_name = category_settings['layer']

            # create a new Layer if it doesn't exist yet
            layer = session.query(Layer).filter_by(name=layer_name).first()

            if not layer:
                layer = Layer(
                    name=layer_name
                    )
            
            # process each file in the category
            for file_name, file_settings in category_settings['files'].items():

                # only process files with the "standard" EPSG_4326 projection
                if "EPSG_4326" in file_name:
                    geojson_path = os.path.join(base_path, category, file_name)
                    geojson_data = load_json(geojson_path)

                    # Get the respective FeatureSet
                    feature_set = session.query(FeatureSet).filter_by(name=file_settings['name']).first()

                    # Create a new FeatureSet if it doesn't exist yet
                    if not feature_set:
                            
                        # create the style and colormap
                        style, colormap = style_to_db(file_settings)

                        # add them to the session
                        session.add(style)
                        if colormap:
                            session.add(colormap)
                        
                        session.commit()

                        # finally, create the feature set
                        feature_set = FeatureSet(
                            name=file_settings['name'],
                            layer=layer,
                            style=style
                        )
                        session.add(feature_set)
                        session.commit()

                    # Process each feature
                    for geojson_feature in geojson_data['features']:

                        feature = feature_to_db(geojson_feature, session)

                        if feature:
                            feature.feature_set = feature_set
                            session.add(feature)

                    session.commit()

def feature_to_db(geojson_feature):
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

def style_to_db(file_settings):
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

    # get all geojson files
    files = get_files()

    n_categories = len(files)
    n_files = sum([len(v) for v in files.values()])

    print(f'Found {n_categories} categories with {n_files} files')

    # transform geojson files to database entries
    if verbose: print("Transfering geojson files into the database... ")
    transform_geojson_to_db(files, session, verbose=verbose)
    if verbose: print("Done!")

    # close the database connection
    session.close()

    if verbose: print("=========================")
    if verbose: print("Database rebuild finished")
    if verbose: print("=========================")

if __name__ == '__main__':
    build(verbose=True)