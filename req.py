# Handling API requests

import requests
import json

ACCEPTED_JSON_TYPES = ['application/json', 'application/geo+json']

def get_api_collections(base_api):
    """
    Returns the collections endpoint from the API base URL
    For example:
    https://api.hamburg.de/datasets/v1/fahrradhaeuschen/
    returns the response from:
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

def get_items_endpoint(collection):
    """
    Returns the correct items endpoint from a collection response
    """

    # check if the request was successful
    collection_links = collection['links']

    # find the link with the rel 'items'
    # and the type 'application/json' or 'application/geo+json'
    for collection_link in collection_links:
        if collection_link['rel'] == 'items' and collection_link['type'] in ACCEPTED_JSON_TYPES:
            return collection_link['href']
        
def request_items(collection, verbose=False):
    """
    Takes in a Collection object from the database and requests the dataset items from the API.
    Returns the GeoJSON response from the API or None if the request failed.
    """

    url = collection.url

    response = requests.get(url)
    if response.status_code == 200:

        response_json = response.json()
        if verbose: print(f'{response_json["numberReturned"]} items returned from {response_json["totalFeatures"]}')

        return response_json
    
    return None

def get_collection_properties(collection):
    """
    This function takes in a Collection object from the database and returns the set of all properties of the features.
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