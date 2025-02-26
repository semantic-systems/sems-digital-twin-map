# This file handles API requests to OGC API Features data sources
# While it is specifically tailored to api.hamburg.de, it should work for other OGC API Features sources as well

import requests
import json

from data.model import Collection, Feature

# the accepted JSON types
ACCEPTED_JSON_TYPES = ['application/json', 'application/geo+json']

def get_api_collections(base_api: str):
    """
    Returns the collections object from the API base URL
    For example:
    https://api.hamburg.de/datasets/v1/fahrradhaeuschen/
    returns the response from:
    https://api.hamburg.de/datasets/v1/fahrradhaeuschen/collections
    """
    # the header we send with our requests
    headers = {'Content-Type': 'application/json'}

    base_response = requests.get(base_api, headers=headers)

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
    
    # if the request failed, return None
    return None

def get_items_endpoint(collection: dict):
    """
    Returns the correct items endpoint from a collection response.\\
    This function searches for the link with the rel 'items'.\\
    If no link is found, None is returned.
    """

    # get the links from the collection
    collection_links = collection['links']

    # find the link with the rel 'items'
    # and the type 'application/json' or 'application/geo+json'
    for collection_link in collection_links:
        if collection_link['rel'] == 'items' and collection_link['type'] in ACCEPTED_JSON_TYPES:
            return collection_link['href']
    
    # if no link was found, return None
    return None

def get_base_endpoint(collection: dict):
    """
    Returns the base endpoint from a collection response.\\
    This function searches for the link with the rel 'self'.\\
    If no link is found, None is returned.
    """

    # get the links from the collection
    collection_links = collection['links']

    # find the link with the rel 'self'
    for collection_link in collection_links:
        if collection_link['rel'] == 'self':
            return collection_link['href']
    
    # if no link was found, return None
    return None
        
def request_items(collection: Collection, verbose=False):
    """
    Takes in a Collection object from the database and requests the dataset items from the API.
    Returns the GeoJSON response from the API or None if the request failed.
    """

    url_items = collection.url_items
    entries = collection.entries

    # also add the limit parameter to the url
    # it controls how many items are returned
    # TODO: if the number of items is large, make multiple smaller requests

    url_items = url_items + f'&limit={entries}'
    response = requests.get(url_items)

    if response.status_code == 200:

        response_json = response.json()
        if verbose: print(f'{collection.identifier} returned {response_json["numberReturned"]} out of {entries} items')

        return response_json
    
    return None

def get_collection_properties(collection: Collection):
    """
    This function takes in a Collection object from the database and returns the set of all properties of its features.
    """

    # a set of all keys
    keys = set()

    features = collection.features

    if features is None:
        return None

    if len(features) == 0:
        return None

    for feature in features:

        current_keys = feature.properties.keys()

        # add all keys to the set
        keys[collection.identifier] = keys[collection.identifier].union(current_keys)

    return keys