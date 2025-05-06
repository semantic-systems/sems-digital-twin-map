import requests
import json

def geolocate(text: str):
    """
    In the future, this will hit the geolocation API and return the Wikidata ID.
    """

    # for now, just load and return output.json
    with open('src/app/layout/map/output.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data

def get_coordinate_location(qid, lang='en'):
    """
    Retrieve the (latitude, longitude) coordinates for a Wikidata entity.

    Parameters:
        qid (str): The Wikidata QID (e.g. "Q6451").
        lang (str): Language code for the labels and descriptions (default is 'en').

    Returns:
        tuple: (title, latitude, longitude) if coordinates are present, else (title, None, None) if no coordinates are found. If an error occurs or no entry was found, returns (None, None, None).
    """

    base_url = "https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items"
    url = f"{base_url}/{qid}"

    try:
        response = requests.get(url, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        data = response.json()

        title = data.get("labels", {}).get(lang, "No title available")
        description = data.get("descriptions", {}).get(lang, "No description available")

        # capitalize the first letter of the description
        description = description.capitalize()

        coord_statements = data.get("statements", {}).get("P625", [])
        if not coord_statements:
            return title, description, None, None

        content = coord_statements[0].get("value", {}).get("content", {})
        lat = content.get("latitude", None)
        lon = content.get("longitude", None)

        return title, description, lat, lon

    except (requests.RequestException, ValueError, KeyError):
        return None, None, None, None