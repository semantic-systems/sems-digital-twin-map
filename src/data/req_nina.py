# Handling API requests to api.hamburg.de

import requests
from datetime import datetime, timedelta
from shapely.geometry import shape
from geoalchemy2 import WKTElement

from data.model import Alert
from data.connect import autoconnect_db

# the endpoint for the nina api
BASE_URL = 'https://warnung.bund.de/api31'

# amtlicher regionalschlüssel for hamburg
# see here: https://www.penultima.de/ars/
ARS = '020000000000'

def save_alerts(ars=ARS):
    """
    Save new all alerts from the nina api for the configured ARS to the database.
    """

    alerts_nina, alerts_details, alerts_geojson = get_alerts()

    alerts_db = []

    # save all alerts to the database
    engine, session = autoconnect_db()

    # get all existing Alerts from the last 30 days
    # to avoid duplicates
    alerts_existing = session.query(Alert).filter(Alert.timestamp > datetime.now() - timedelta(days=30)).all()

    # get the hashes of the existing alerts
    hashes_existing = [alert.hash for alert in alerts_existing]

    for alert_nina in alerts_nina:
        # compare the hash of the alert to the existing hashes
        if alert_nina['payload']['hash'] in hashes_existing:
            print(f'Recieved duplicate alert, skipping... (hash={alert_nina["payload"]["hash"]})')
            continue

        alert_db = create_alert(alert_nina, alerts_details, alerts_geojson)
        alerts_db.append(alert_db)
        print(f'Saved new alert (hash={alert_nina["payload"]["hash"]})')

    session.add_all(alerts_db)
    session.commit()

    session.close()
    engine.dispose()

    return alerts_db

def get_alerts(ars=ARS):
    """
    Get all alerts from the nina api for the configured ARS
    """

    # get all alerts from the nina api dashboard
    url = BASE_URL + "/dashboard/" + ars + ".json"

    response = requests.get(url)
    alerts_dashboard = response.json()

    ids = [alert['id'] for alert in alerts_dashboard]

    alerts_details = []
    alert_geojson = []

    # for each alert, get the details and geojson area
    for id in ids:
        json_url = BASE_URL + "/warnings/" + id + ".json"
        geojson_url = BASE_URL + "/warnings/" + id + ".geojson"

        json_response = requests.get(json_url)
        alerts_details.append(json_response.json())

        geojson_reponse = requests.get(geojson_url)
        alert_geojson.append(geojson_reponse.json())
    
    return alerts_dashboard, alerts_details, alert_geojson

def create_alert(alert_dashboard, alert_details, alert_geojson):
    """
    Create a new Alert database object for a single NINA alert.
    """

    alert_details = alert_details[0]
    alert_geojson = alert_geojson[0]['features'][0]['geometry']

    # extract nested data
    # db -> alert_dashboard
    # dt -> alert_details
    db_payload = alert_dashboard['payload']
    db_data = db_payload['data']

    print(alert_details)

    dt_info = alert_details['info'][0]
    dt_parameter = dt_info['parameter']

    # convert alert_geojson into Shapely geometry
    shapely_geom = shape(alert_geojson)

    # Use Shapely geometry with `geoalchemy2`
    geometry_type = shapely_geom.geom_type
    wkt_geometry = shapely_geom.wkt
    srid = 4326
    geometry_element = WKTElement(wkt_geometry, srid)

    # get the datetime from the alert
    time_sent = datetime.fromisoformat(alert_dashboard['sent'])

    # find the ZGEM parameter in dt_parameters
    zgem = None

    for parameter in dt_parameter:
        if parameter['valueName'] == 'ZGEM':
            zgem = parameter['value']

    alert_db = Alert(
        api_identifier = alert_dashboard['id'],
        hash = db_payload['hash'],

        sender = alert_details['sender'],
        timestamp = time_sent,
        status = alert_details['status'],
        msg_type = alert_details['msgType'],
        scope = alert_details['scope'],

        category = dt_info['category'][0],
        event = dt_info['event'],
        urgency = dt_info['urgency'],
        severity = dt_info['severity'],
        certainty = dt_info['certainty'],

        sender_name = dt_info['senderName'],
        headline = dt_info['headline'],
        description = dt_info['description'],
        web = dt_info['web'],
        contact = dt_info['contact'],

        geometry = geometry_element,
        area_description = dt_info['area'][0]['areaDesc'],

        zgem = zgem    
    )

    return alert_db