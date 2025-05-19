import requests
import json

SERVER_URL = "http://134.100.14.190:8001/predict_text"
HEADERS = {"Content-Type": "application/json"}

PREDICTED_LABELS = {
    'affected_individual': 'Affected Individual',
    'caution_and_advice': 'Caution and Advice',
    'displaced_and_evacuations': 'Displaced and Evacuations',
    'donation_and_volunteering': 'Donation and Volunteering',
    'infrastructure_and_utilities_damage': 'Infrastructure and Utilities Damage',
    'injured_or_dead_people': 'Injured or Dead People',
    'missing_and_found_people': 'Missing and Found People',
    'not_humanitarian': 'Not Humanitarian',
    'requests_or_needs': 'Requests or Needs',
    'response_efforts': 'Response Efforts',
    'sympathy_and_support': 'Sympathy and Support'
}

def geolocate(text: str):
    """
    This hits the geolocation server with the given text and returns the response.
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
