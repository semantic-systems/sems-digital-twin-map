import requests
import json

SERVER_URL = "http://134.100.14.190:8001/predict_text"
HEADERS = {"Content-Type": "application/json"}

PREDICTED_LABELS = {
    'affected_individual': 'Betroffene Personen',
    'caution_and_advice': 'Warnung und Hinweise',
    'displaced_and_evacuations': 'Evakuierungen und Vertriebenenhilfe',
    'donation_and_volunteering': 'Spenden und Freiwilligenarbeit',
    'infrastructure_and_utilities_damage': 'Schäden an Infrastruktur und Versorgung',
    'injured_or_dead_people': 'Verletzte oder Tote',
    'missing_and_found_people': 'Vermisste und gefundene Personen',
    'not_humanitarian': 'Nicht-humanitäres Ereignis',
    'requests_or_needs': 'Hilfsgesuche oder Bedürfnisse',
    'response_efforts': 'Hilfs- und Rettungsmaßnahmen',
    'sympathy_and_support': 'Anteilnahme und Unterstützung'
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
