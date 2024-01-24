# Launches the event server

from flask import Flask, request, jsonify
from datetime import datetime

# internal imports
from data.build import feature_to_obj
from data.connect import autoconnect_db
from data.model import FeatureSet, Feature, Style, Layer

app = Flask(__name__)

# test commands
# curl -X POST -H "Content-Type: application/json" -d "{\"event\": {\"timestamp\": 1609459200.0, \"event_type\": \"earthquake\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [125.6, 10.1]}}, \"predictions\": [{\"timestamp\": 1609459300.0, \"event_type\": \"aftershock\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [125.7, 10.2]}}]}" http://localhost:8051/eventserver
# curl -X POST -H "Content-Type: application/json" "localhost:8051/eventserver" -d "{\"event\":{\"timestamp\":1704453251,\"event_type\":\"Überschwemmung\",\"geometry\":{\"type\":\"MultiPolygon\",\"coordinates\":[[[[9.805151976237221,53.56389856394301],[9.805228354115075,53.56389265651229],[9.805376979093932,53.56388117493709],[9.80539691039598,53.56387963848051],[9.805421485829001,53.56404228779252],[9.805485852452774,53.56446827574004],[9.805492193590066,53.56451037269882],[9.80526023521814,53.56456874388791],[9.805151976237221,53.56389856394301]]]]}},\"predictions\":[{\"timestamp\":1704453252,\"event_type\":\"Überschwemmung\",\"geometry\":{\"type\":\"MultiPolygon\",\"coordinates\":[[[[9.805421485829001,53.56404228779252],[9.806024310264133,53.56401005625513],[9.806050355709857,53.56424989165918],[9.8060540327049,53.564283664904146],[9.806057767300466,53.56431808495685],[9.805485852452774,53.56446827574004],[9.805421485829001,53.56404228779252]]]]}},{\"timestamp\":1704453252,\"event_type\":\"Überschwemmung\",\"geometry\":{\"type\":\"MultiPolygon\",\"coordinates\":[[[[9.80526023521814,53.56456874388791],[9.80522374165269,53.56457751995856],[9.805171947235403,53.56458997656815],[9.805134114785455,53.56430405368117],[9.804926237927074,53.56431779436748],[9.8048943590149,53.56431990552546],[9.804856267158124,53.564322427021544],[9.804690417862597,53.56433338560875],[9.804654603060136,53.56433575688982],[9.804630286966155,53.564146849304926],[9.804769731736847,53.564141668491665],[9.804890588050366,53.5641371878819],[9.804904091898583,53.564136683529114],[9.804883074187845,53.56399590698324],[9.804862351828277,53.563857159920346],[9.805068685402073,53.563844957826184],[9.805077543092109,53.56390431441464],[9.805118282129287,53.56390207166073],[9.80511815938363,53.56390117360334],[9.805151976237221,53.56389856394301],[9.80526023521814,53.56456874388791]]]]}}]}"
@app.route('/eventserver', methods=['POST'])
def receive_data(verbose=True):

    # Parse received JSON data
    data = request.json
    event = data['event']
    predictions = data['predictions']

    if verbose: print('Received data:')
    if verbose: print(f'Event with type {event["event_type"]} at {event["timestamp"]}')#
    if verbose: print(f'With {len(predictions)} Predictions')

    # connect to the database
    if verbose: print('Connecting to database...', end='')
    engine, session = autoconnect_db()
    if verbose: print('Done')

    # find the layer and style with the names 'Events'
    # TODO: later this should be replaced with a query to find the layer and style with the same name as the event_type
    if verbose: print('Creating FeatureSet...', end='')
    db_layer_events = session.query(Layer).filter(Layer.name == 'Events').first()
    db_layer_predictions = session.query(Layer).filter(Layer.name == 'Predictions').first()
    db_style_events = session.query(Style).filter(Style.name == 'Events').first()
    db_style_predictions = session.query(Style).filter(Style.name == 'Predictions').first()


    if db_layer_events is None:
        if verbose: print('No Layer with name "Events" found!')
        return jsonify({'status': 'error', 'message': 'Internal Server Error: No Layer with name "Events" found'})

    if db_layer_predictions is None:
        if verbose: print('No Layer with name "Predictions" found!')
        return jsonify({'status': 'error', 'message': 'Internal Server Error: No Layer with name "Predictions" found'})
    
    if db_style_events is None:
        if verbose: print('No Style with name "Events" found!')
        return jsonify({'status': 'error', 'message': 'Internal Server Error: No Style with name "Events" found'})
    
    if db_style_predictions is None:
        if verbose: print('No Style with name "Predictions" found!')
        return jsonify({'status': 'error', 'message': 'Internal Server Error: No Style with name "Predictions" found'})

    # create a FeatureSet for the event and predictions
    db_feature_set_event = FeatureSet(
        name='Event',
        layer=db_layer_events,
        style=db_style_events,
        collection=None
    )

    db_feature_set_prediction = FeatureSet(
        name='Prediction',
        layer=db_layer_predictions,
        style=db_style_predictions,
        collection=None
    )

    # save the FeatureSet to the database
    session.add(db_feature_set_event)
    session.add(db_feature_set_prediction)
    session.commit()
    if verbose: print('Done')

    # Convert JSON data to database objects
    if verbose: print('Creating Features from Event and Predictions...', end='')

    event_type = event['event_type']
    event_timestamp = event['timestamp']
    # transform the timestamp into a datetime string of format HH:MM:SS DD.MM.YYYY
    event_datetime = datetime.fromtimestamp(event_timestamp).strftime('%H:%M:%S %d.%m.%Y')

    feature_properties = {
        'event_type': event_type,
        'time': event_datetime,
        'timestamp': event_timestamp
    }

    # save the properties in the event
    event['properties'] = feature_properties

    # create a Feature object from the event
    db_event = feature_to_obj(event)

    db_predictions = []

    # now the same for the predictions
    # TODO: put the redundancy into its own function
    for prediction in predictions:
        prediction_type = prediction['event_type']
        prediction_timestamp = prediction['timestamp']

        # transform the timestamp into a datetime string of format HH:MM:SS DD.MM.YYYY
        prediction_datetime = datetime.fromtimestamp(prediction_timestamp).strftime('%H:%M:%S %d.%m.%Y')

        feature_properties = {
            'event_type': prediction_type,
            'time': prediction_datetime,
            'timestamp': prediction_timestamp
        }

        # save the properties in the prediction
        prediction['properties'] = feature_properties

        # create a Feature object from the prediction
        db_predictions.append(feature_to_obj(prediction))

    # check if all objects are valid
    if db_event is None:
        if verbose: print('Invalid event data!')
        return jsonify({'status': 'error', 'message': 'Invalid event data'})
    
    if None in db_predictions:
        if verbose: print('One or more invalid prediction entries!')
        return jsonify({'status': 'error', 'message': 'One or more invalid prediction entries'})
    
    # set the events and predictions FeatureSets
    db_event.feature_set = db_feature_set_event
    for prediction in db_predictions:
        prediction.feature_set = db_feature_set_prediction
    
    if verbose: print('Done')
    
    # save the event and predictions to the database
    if verbose: print('Saving Event and Predictions to database...', end='')
    session.add(db_event)
    session.add_all(db_predictions)
    session.commit()
    if verbose: print('Done')

    # close the session
    if verbose: print('Closing database connection...', end='')
    session.close()
    engine.dispose()
    if verbose: print('Done')

    # return jsonify(data)
    if verbose: print("Success! Returning {'status': 'success'}")
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051)