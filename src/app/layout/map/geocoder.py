import requests
import json

SERVER_URL = "http://sems-kg-1:8001/predict_text"
HEADERS = {"Content-Type": "application/json"}

def geolocate(text: str):
    """
    In the future, this will hit the geolocation API and return the result.
    """

    data = {
        "text": text
    }

    try:
        response = requests.post(SERVER_URL, headers=HEADERS, json=data)
        response.raise_for_status()  # Raise an error for bad responses
        result = response.json()
        return result
    
    except requests.exceptions.RequestException as e:
        print(f"[Geolocation] RequestException: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[Geolocation] Error decoding JSON: {e}")
        return None
    except Exception as e:
        print(f"[Geolocation] An unexpected error occurred: {e}")
        return None