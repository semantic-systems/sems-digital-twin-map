from datetime import date, timedelta, datetime
from datetime import datetime
import json

from dash import Dash, html, dcc, Output, Input, State, callback_context, MATCH, ALL
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

from sqlalchemy import inspect

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario, Report
from data.connect import autoconnect_db
from data.build import build, refresh
from app.convert import layer_id_to_layer_group, scenario_id_to_layer_group, style_to_dict

def build_layer_checkboxes():
    """
    Build the layer checkboxes for the layers control.
    Format: `[{'label': 'Layer Display Name', 'value': 'Layer ID'}]`
    """

    # get all available layers sets
    engine, session = autoconnect_db()

    # Check if the Layer table exists
    inspector = inspect(engine)
    if 'layers' not in inspector.get_table_names():
        # Close database connection and return empty list if Layer does not exist
        session.close()
        engine.dispose()
        print("Warning: Table 'layers' does not exist. No Layer checkboxes will be created. You can rebuild the database by running 'python main.py -rebuild'. See more information with 'python main.py -help'.")
        return []

    layers = session.query(Layer).all()

    layer_checkboxes = [{'label': layer.name, 'value': layer.id} for layer in layers]

    # close database connection
    session.close()
    engine.dispose()

    return layer_checkboxes

def build_scenario_checkboxes():
    """
    Build the scenario checkboxes for the scenario control.
    Format: `[{'label': 'Scenario Display Name', 'value': 'Scenario ID'}]`
    """

    # get all available layers sets
    engine, session = autoconnect_db()

    # Check if the Layer table exists
    inspector = inspect(engine)
    if 'scenarios' not in inspector.get_table_names():
        # Close database connection and return empty list if Layer does not exist
        session.close()
        engine.dispose()
        print("Warning: Table 'scenarios' does not exist. No Layer checkboxes will be created. You can rebuild the database by running 'python main.py -rebuild'. See more information with 'python main.py -help'.")
        return []

    scenarios = session.query(Scenario).all()

    scenario_checkboxes = [{'label': scenario.name, 'value': scenario.id} for scenario in scenarios]

    # close database connection
    session.close()
    engine.dispose()

    return scenario_checkboxes

def highlight_events_predictions(hash, map_children, hide_other=False):
    """
    Highlights all events and predictions with the same hash.
    - hash: The hash to highlight
    - map_children: The map children to iterate over
    - hide_other: If True, hides all events and predictions with a different hash
    """

    ctx = callback_context

    if not ctx.triggered:
        print("No trigger")
        raise PreventUpdate

    # connect to the db
    engine, session = autoconnect_db()

    # get the styles for later
    # this first gets the styles from the database, then converts them to dictionaries that can be used in the map children
    style_event_default = style_to_dict(session.query(Style).filter(Style.name == 'Events').first())
    style_event_highlight = style_to_dict(session.query(Style).filter(Style.name == 'Events Selected').first())
    style_prediction_default = style_to_dict(session.query(Style).filter(Style.name == 'Predictions').first())
    style_prediction_highlight = style_to_dict(session.query(Style).filter(Style.name == 'Predictions Selected').first())

    session.close()
    engine.dispose()


    # iterate over all children, change the following:
    # - if the child is a Event or Prediction with a different hash, change the color to the default color
    # - if the child is a Event or Prediction with the same hash, change the color to the highlight color
    # - else do nothing

    for child in map_children:

        id = child['props']['id']

        # check if the child is a layer group
        # layer groups have an id that starts with 'layer' or 'scenario'
        if id.startswith('layer'):

            features = child['props']['children']
            new_features = []

            for feature in features:

                feature_id_dict = feature['props']['id']

                if type(feature_id_dict) == str:
                    # skip features which id is just a string
                    continue

                # split something like this: {'type': 'geojson', 'id': 'events-4365'}
                # into feature_type = 'events' and feature_id = '4365'
                feature_type, feature_id = feature_id_dict['id'].split('-')

                if feature_type in ['events', 'predictions']:

                    feature_properties = feature['props']['data']['properties']

                    if 'hash' in feature_properties:

                        if feature_properties['hash'] == hash:

                            # same hash, highlight styling
                            if feature_type == 'events':
                                feature['props']['style'] = style_event_highlight
                            else:
                                feature['props']['style'] = style_prediction_highlight
                            
                            new_features.append(feature)

                        else:
                            # different hash, default styling
                            if feature_type == 'events':
                                feature['props']['style'] = style_event_default
                            else:
                                feature['props']['style'] = style_prediction_default

                            # only append if we dont want to hide other features
                            if not hide_other:
                                new_features.append(feature)
            
            child['props']['children'] = new_features
                
    
    return map_children



def get_layout_map():
    """
    Returns the layout for the map app. Callbacks need to be configured separately.
    This gets set as the child of a dcc.Tab in the main app.
    """

    # build the option checkboxes
    layer_checkboxes = build_layer_checkboxes()
    scenario_checkboxes = build_scenario_checkboxes()

    layout_map = [
        dl.Map(
            children = [
                dl.TileLayer(
                    url='https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/de_basemapde_web_raster_farbe/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png',
                    attribution='&copy; <a href="https://basemap.de/">basemap.de</a>',
                    id='tile_layer'
                )
            ],
            zoom=12,
            doubleClickZoom=False,
            center=(53.55, 9.99),
            style={
                'width': '100%', 
                'height': '100%',
                'z-index': '0'
            },
            id='map'
            ),
        html.Div(                                   # here we create a 'fake' layers control that looks identical to dash-leaflet, but gives us more control
            [
                html.Div(
                    children=[
                        # Hide the Rebuild button from the user
                        # html.Button(
                        #     children="Rebuild",
                        #     id="button_rebuild",
                        #     style={
                        #         "padding": "10px 20px 10px 20px",
                        #         "margin": "5px"
                        #     }
                        # ),
                        html.Button(
                            children="Refresh",
                            id="button_refresh_items",
                            className='button-common',
                            style={
                                "padding": "10px 20px 10px 20px",
                                "margin": "5px"
                            }
                        ),
                        html.Button(
                            children="Update Menu",
                            id="button_update_menu",
                            className='button-common',
                            style={
                                "padding": "10px 20px 10px 20px",
                                "margin": "5px"
                            }
                        )
                    ],
                    style={
                        "display": "flex",
                        "flex-wrap": "wrap",
                        "justify-content": "center",
                        "align-items": "center"
                    }
                ),
                dcc.Tabs(
                    id='map-tabs',
                    children=[
                    dcc.Tab(
                        label='Layers',
                        children=[
                            dcc.Checklist(
                                id='overlay_checklist',
                                options=layer_checkboxes,
                                value=[]
                            )
                        ]
                    ),
                    dcc.Tab(
                        label='Scenarios',
                        children=[
                            dcc.Checklist(
                                id='scenario_checklist',
                                options=scenario_checkboxes,
                                value=[]
                            )
                        ]
                    )
                ]),
                html.Hr(
                    style={
                        'margin': '5px 4px 5px 4px',
                        'border': '0',
                        'border-bottom': '1px solid #777'
                    }
                ),
                dcc.Checklist(
                    id='options_checklist',
                    options=[
                        {'label': 'Hide Features with Timestamp', 'value': 'hide_with_timestamp'},
                        {'label': 'Hide Features without Timestamp', 'value': 'hide_without_timestamp'},
                        {'label': 'Filter by Timestamp', 'value': 'filter_by_timestamp'}
                        ],
                    value=[]
                )                    
            ],
            style={
                'position': 'absolute',
                'float': 'right',
                'margin': '10px',
                'background-color': 'white',
                'border': '1px solid #ccc',
                'padding': '10px',
                'box-shadow': '0 2px 4px rgba(0,0,0,0.1)',
                'border-radius': '5px',
                'max-height': '700px',
                'overflow-y': 'auto',
                'z-index': '1000',
                'right': '0',
                'top': '60px',
                'width:': '200px',
                'color': '#333'
            }
        ),
        html.Div(
            children=[
                # DatePickerRange component
                dcc.DatePickerRange(
                    id='event_range_picker',
                    with_portal=True,
                    display_format='DD.MM.YYYY',
                    minimum_nights=1,
                    clearable=True
                ),
                # Div wrapper for RangeSlider component
                html.Div(
                    dcc.RangeSlider(
                        id='slider_events',
                        min=0,
                        max=100,
                        step=1.0/24.0,  # 1 hour steps
                        value=[25, 75],
                        marks={
                            0: 'XX.XX.XXXX',
                            100: 'XX.XX.XXXX'
                        },
                        updatemode='mouseup'    # update the slider value when the mouse is released
                    ),
                    style={
                        'flex': '1',  # Allows the range slider to grow as needed within the flex container
                        'margin-left': '10px'
                    }
                ),
                html.Div( # shows the selected event range
                    id='event_range_text',
                    children=[
                        html.Div(
                            html.U(
                                children='Selected',
                                style={
                                    'font-size': '14pt',
                                    'font-weight': 'bold',
                                    'margin': '4px 2px 0px 2px',
                                }
                            ),
                            style={
                                'text-align': 'center'
                            }
                        ),
                        html.P(
                            children=[
                            'XX:XX XX.XX.XXXX -',
                            html.Br(),
                            'XX:XX XX.XX.XXXX'
                        ],
                        style={
                            'font-size': '14pt',
                            'font-weight': 'bold',
                            'margin': '2px 2px 0px 2px'
                        }
                        )
                    ],
                    style={
                        'margin-left': '20px',
                        'font-size': '14pt',
                        'font-weight': 'bold',
                        'text-align': 'left',
                        'font-family': '"Courier New", monospace',
                        'color': '#333',
                        'padding': '5px',
                        'border-radius': '4px',
                        'background-color': '#f3f3f3',
                        'display': 'inline-block',
                        'box-shadow': '0px 2px 4px rgba(0, 0, 0, 0.1)'
                    }
                ),
            ],
            style={
                'display': 'flex',
                'align-items': 'center',
                'justify-content': 'space-between',
                'position': 'absolute',
                'left': '0',
                'right': '0',
                'bottom': '0',
                'margin': '10px',
                'background-color': 'white',
                'border': '1px solid #ccc',
                'padding': '10px',
                'box-shadow': '0 2px 4px rgba(0,0,0,0.1)',
                'border-radius': '5px',
                'z-index': '1000',
                'color': '#333'
            }
        ),
        html.Div(
            id='rss_headlines',
            children=[
                html.P(
                    children='Headlines',
                    style={
                        'font-size': '14pt',
                        'font-weight': 'bold',
                        'margin': '4px 2px 4 2px',
                        'text-align': 'center'
                    }
                ),
                html.Ul(
                    id='rss_headlines_list',
                    children=[
                        html.Li(
                            html.A(
                                children='RSS Headline',
                                href='https://example.com',
                                target='_blank'
                            ),
                        ),
                        html.Li( 
                            html.A(
                                children='Tiny',
                                href='https://example.com',
                                target='_blank'
                            ),
                        ),
                        html.Li( 
                            html.A(
                                children='Looooong Headline',
                                href='https://example.com',
                                target='_blank'
                            ),
                        ),
                        html.Li( 
                            html.A(
                                children='SUPER LONG HEADLINE THAT IS SO LONG IT WILL BREAK THE LAYOUT AND MAKE EVERYTHING LOOK UGLY',
                                href='https://example.com',
                                target='_blank'
                            )
                        )
                    ],
                    style={
                        # increase child seperator
                        'margin': '0',
                        'padding': '0',
                        'list-style-type': 'none'
                    }
                )
            ],
            style={
                'position': 'absolute',
                'top': '150px',
                'left': '0',
                'float': 'left',
                'background-color': 'white',
                'border': '1px solid #ccc',
                'border-radius': '5px',
                'margin': '10px',
                'padding': '10px',
                'box-shadow': '0 2px 4px rgba(0,0,0,0.1)',
                'z-index': '1000',
                'max-height': '660px',
                'overflow-y': 'auto',
                'width': '250px',
            }
        ),
        dcc.Store(id='event_range_full', data=[]),                 # the full event range, selected by event_range_picker
        dcc.Store(id='event_range_selected', data=[]),             # the selected event range, selected by slider_events
        dcc.Interval(id='interval_refresh_rss', interval=3600000 , n_intervals=0),  # refresh the rss feed every hour
        html.Div(id='dummy_output_1', style={'display': 'none'})  # for some reason callback functions always need an output, so we create a dummy output for functions that dont return anything
    ]
    
    return layout_map

def callbacks_map(app: Dash):
    """
    Links the dash app with the necessary callbacks.
    Pass the Dash app as an argument.
    """

    # this big function is a callback that updates the map children
    # meaning, we create/modify/delete markers and polygons on the map
    @app.callback(
        [
            Output('map', 'children')
        ],
        [
            Input('overlay_checklist', 'value'),        # triggered when a layer is selected or deselected
            Input('scenario_checklist', 'value'),       # triggered when a scenario is selected or deselected
            Input('options_checklist', 'value'),        # triggered when the options checklist changes
            Input('event_range_selected', 'data'),      # triggered when a different event range is selected
            Input('map-tabs', 'value')                  # triggered when the tab value changes
        ],
        [
            State('map', 'children'),
        ]
    )
    def update_map(overlay_checklist_value, scenario_checklist_value, options_checklist_value, event_range_selected_data, map_tabs_value, map_children):
        """
        This callback is triggered on the following events:
        - A layer is selected or deselected in the overlay_checklist
        - A scenario is selected or deselected in the scenario_checklist
        - The options checklist changes
        - A different event range is selected
        - The tab value changes

        It updates the map children, meaning it deletes all existing marker/polygon objects and creates new ones from the Features in the database.
        """

        # first, divide the map children into layer groups and non-layer groups
        # we keep the non-layer groups (i.e. the tilemap) and delete the layer groups (markers and polygons)
        # afterwards, we create new layer groups and add them to the map children
        map_children_no_layergroup = []
        map_children_layergroup = []

        for child in map_children:

            id = child['props']['id']

            # check if the child is a layer group
            # layer groups have an id that starts with 'layer' or 'scenario'
            if id.startswith('layer') or id.startswith('scenario'):
                map_children_layergroup.append(child)
            else:
                map_children_no_layergroup.append(child)
        
        # TODO: modifying the layer groups can be done more efficiently by only adding/removing the layer groups affected by the change, not rebuilding them from scratch
        # but i will warn you, it will cost you a lot of time and nerves (as it has me already)
        # here, we take the easy way and just delete all layer groups and create new ones
        
        # delete all current layer groups (meaning, delete all existing markers and polygons)
        map_children_layergroup = []

        # the selected options
        hide_with_timestamp: bool = 'hide_with_timestamp' in options_checklist_value
        hide_without_timestamp: bool = 'hide_without_timestamp' in options_checklist_value
        filter_by_timestamp: bool = 'filter_by_timestamp' in options_checklist_value

        # we are in the Layers tab
        if map_tabs_value == 'tab-1':
            for overlay in overlay_checklist_value:
                if filter_by_timestamp:
                    # get the layer group with the event range data
                    layer_group = layer_id_to_layer_group(overlay, event_range_selected_data, hide_with_timestamp, hide_without_timestamp)
                else:
                    # get the layer group without the event range data
                    layer_group = layer_id_to_layer_group(overlay, None, hide_with_timestamp, hide_without_timestamp)

                # add the layer group to the map
                map_children_layergroup.append(layer_group)
        
        # we are in the Scenarios tab
        elif map_tabs_value == 'tab-2':
            for scenario in scenario_checklist_value:
                if filter_by_timestamp:
                    # get the layer group with the event range data
                    layer_group = scenario_id_to_layer_group(scenario, event_range_selected_data, hide_with_timestamp, hide_without_timestamp)
                else:
                    # get the layer group without the event range data
                    layer_group = scenario_id_to_layer_group(scenario, None, hide_with_timestamp, hide_without_timestamp)

                # add the layer group to the map
                map_children_layergroup.append(layer_group)
        
        else:
            # unknown tab selected, do nothing
            raise PreventUpdate

        return [map_children_no_layergroup + map_children_layergroup]

    # if a new event range was selected, update the event_range marks
    @app.callback(
        [
            Output('slider_events', 'marks'),
            Output('slider_events', 'min'),
            Output('slider_events', 'max'),
            Output('slider_events', 'value'),
            Output('event_range_full', 'data')
        ],
        [
            Input('event_range_picker', 'start_date'),
            Input('event_range_picker', 'end_date')
        ],
    )
    def update_slider_marks(start_date_str, end_date_str):
        """
        This callback is triggered when the event_range_picker date range changes.
        It updates the slider marks, the min and max values of the slider, the slider value,
        and stores the new event range in the dcc.Store component.
        """
        
        if start_date_str is None or end_date_str is None:
            # If no dates are selected, raise PreventUpdate to stop the callback from firing
            raise PreventUpdate
        
        # Convert string dates to date objects
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        # Calculate the total number of days in the range
        total_days = (end_date - start_date).days

        # Update the slider's minimum and maximum values to match the total days
        min_value = 0
        max_value = total_days

        # Create the slider marks at 25% intervals
        slider_marks = {
            min_value: start_date.strftime('%d.%m.%Y'),
            int(total_days * 0.25): (start_date + timedelta(days=int(total_days * 0.25))).strftime('%d.%m.%Y'),
            int(total_days * 0.5): (start_date + timedelta(days=int(total_days * 0.5))).strftime('%d.%m.%Y'),
            int(total_days * 0.75): (start_date + timedelta(days=int(total_days * 0.75))).strftime('%d.%m.%Y'),
            max_value: end_date.strftime('%d.%m.%Y'),
        }

        # Set the slider value to the full range
        slider_value = [min_value, max_value]

        # Update the dcc.Store with the new date range
        event_range_full_data = {'start': start_date_str, 'end': end_date_str}

        return slider_marks, min_value, max_value, slider_value, event_range_full_data

    @app.callback(
        [Output('event_range_text', 'children'), Output('event_range_selected', 'data', allow_duplicate=True)],
        [Input('slider_events', 'value')],
        [State('event_range_full', 'data')],
        prevent_initial_call=True
    )
    def display_slider_value(value, event_range_full_data):
        """
        This callback is triggered when the slider value changes.
        It changes the event range text and updates the selected event range data.
        """

        # If no event range data is available, raise PreventUpdate to stop the callback from firing
        if event_range_full_data is None:
            print("No event range data found. Stopping selected event range update.")
            raise PreventUpdate
        
        if type(event_range_full_data) == list:
            print("No event range data found. Stopping selected event range update.")
            raise PreventUpdate
        
        if value is None:
            print("No slider value available. Stopping selected event range update.")
            raise PreventUpdate
            
        # Convert string dates to datetime objects
        start_datetime = datetime.fromisoformat(event_range_full_data['start'])
        end_datetime = datetime.fromisoformat(event_range_full_data['end'])

        # Calculate the new start and end times based on the slider values
        new_start_datetime = start_datetime + timedelta(days=value[0])
        new_end_datetime = start_datetime + timedelta(days=value[1])

        event_range_selected_data = {'start': new_start_datetime, 'end': new_end_datetime}

        # Update the event range text
        event_range_text = [
            html.Div(
                html.U(
                    children='Selected',
                    style={
                        'font-size': '14pt',
                        'font-weight': 'bold',
                        'margin': '4px 2px 0px 2px',
                    }
                ),
                style={
                    'text-align': 'center'
                }
            ),
            html.P(
                children=[
                    new_start_datetime.strftime('%H:%M %d.%m.%Y') + ' -',
                    html.Br(),
                    new_end_datetime.strftime('%H:%M %d.%m.%Y')
                ],
                style={
                    'font-size': '14pt',
                    'font-weight': 'bold',
                    'margin': '4px 2px 0px 2px'
                }
            )
        ]

        return event_range_text, event_range_selected_data

    # call api to refresh the database
    @app.long_callback(
        [
            Output('dummy_output_1', 'children')
        ],
        [
            Input('button_refresh_items', 'n_clicks')
        ],
        running=[
            (Output("button_refresh_items", "disabled"), True, False),
        ],
    )
    def refresh_items(n_clicks):
        """
        This callback is triggered when the refresh button is clicked.
        It calls the refresh() function from build.py to update the database.
        """

        # if the refresh button was not clicked, do nothing
        if n_clicks is None:
            raise PreventUpdate
        
        engine, session = autoconnect_db()

        # call the reload function
        refresh(session, True)

        # close database connection
        session.close()
        engine.dispose()
        
        raise PreventUpdate

        # return nothing
        return []
    
    # call function to update the menu
    # updates the values of the layer and scenario checkboxes
    @app.callback(
        [Output('overlay_checklist', 'options', allow_duplicate=True), Output('scenario_checklist', 'options')],
        [Input('button_update_menu', 'n_clicks')],
        prevent_initial_call=True
    )
    def update_menu(n_clicks):
        """
        This callback is triggered when the update menu button is clicked.
        It updates the values of the layer and scenario checkboxes.
        """

        # if the update menu button was not clicked, do nothing
        if n_clicks is None:
            raise PreventUpdate

        # update the layer and scenario checkboxes
        layer_checkboxes = build_layer_checkboxes()
        scenario_checkboxes = build_scenario_checkboxes()

        # return the updated layer and scenario checkboxes
        return [layer_checkboxes, scenario_checkboxes]
    
    # on click on a event or prediction geojson feature
    # change the color of all other features with the same hash
    @app.callback(
        Output('map', 'children', allow_duplicate=True),
        [
            Input({'type': 'geojson', 'id': ALL}, 'n_clicks'),
            Input({'type': 'geojson', 'id': ALL}, 'clickData')
        ],  
        [
            State('map', 'children')
        ],
        prevent_initial_call=True
    )
    def highlight_prediction(n_clicks, click_data, map_children):
        """
        This callback is triggered when a feature is clicked.
        It changes the color of all other features with the same hash.
        Basically just a wrapper around highlight_events_predictions.
        """

        # because all features fire when they are created, we need to check if a click was actually made
        # we get back an array of clicks for every feature that is able to trigger this function
        # if all clicks are None, no click was made and the callback was triggered by the creation of the features
        # if that happens, we raise PreventUpdate to stop the callback from firing
        if all([n is None for n in n_clicks]):
            raise PreventUpdate

        if click_data is None:
            raise PreventUpdate
        
        if n_clicks is None:
            raise PreventUpdate

        # get the callback content, to get the trigger id
        # we use this id to find the correct database feature
        # and use that features hash to highlight all other features with the same hash
        ctx = callback_context

        if not ctx.triggered:
            raise PreventUpdate
        
        trigger_id = json.loads(ctx.triggered[0]['prop_id'].split('.')[0])
    
        # if we get here, we have a valid click on a prediction feature
        trigger_type, trigger_number = trigger_id['id'].split('-')
    
        # connect to the db
        engine, session = autoconnect_db()

        if trigger_type == 'events':
            feature_hash = session.query(Feature).filter(Feature.id == trigger_number).first().properties['hash']
        elif trigger_type == 'predictions':
            feature_hash = session.query(Feature).filter(Feature.id == trigger_number).first().properties['hash']
        else:
            print(f"Invalid trigger type {trigger_type} in highlight_prediction")
            raise PreventUpdate
        
        # close database connection
        session.close()
        engine.dispose()

        # highlight all features with the same hash
        map_children = highlight_events_predictions(feature_hash, map_children)

        return map_children

    # on double click, hide all other predictions
    @app.callback(
        Output('map', 'children', allow_duplicate=True),
        [
            Input({'type': 'geojson', 'id': ALL}, 'n_clicks'),
            Input({'type': 'geojson', 'id': ALL}, 'dblclickData')
        ],  
        [
            State('map', 'children')
        ],
        prevent_initial_call=True
    )
    def hide_other_predictions(n_clicks, dbl_click_data, map_children):
        """
        This callback is triggered when a feature is clicked.
        It changes the color of all other features with the same hash.
        Basically just a wrapper around highlight_events_predictions.
        """

        if dbl_click_data is None:
            print("s0")
            raise PreventUpdate
        
        if n_clicks is None:
            print("s1")
            raise PreventUpdate
        
        if all([n is None for n in n_clicks]):
            print("s2")
            raise PreventUpdate

        # get the callback content, to get the trigger id
        # we use this id to find the correct database feature
        # and use that features hash to highlight all other features with the same hash
        ctx = callback_context

        if not ctx.triggered:
            print("s3", ctx.triggered)
            raise PreventUpdate
        
        feature_hash = None
        
        for click_element in dbl_click_data:

            print(click_element)


            if click_element is None:
                continue

            feature_hash = click_element['properties']['hash']
            break

        if feature_hash is None:
            print("s4")
            raise PreventUpdate

        # hide all features with a different hash
        map_children = highlight_events_predictions(feature_hash, map_children, hide_other=True)

        return map_children
    
    # update the rss headlines
    @app.callback(
        Output('rss_headlines_list', 'children'),
        [Input('interval_refresh_rss', 'n_intervals')],
    )
    def update_rss_headlines(n_clicks):
        """
        This callback is triggered when the refresh button is clicked.
        It updates the RSS headlines list.
        """

        def headline_to_li(headline, href):
            """
            Converts a headline string to a html list item.
            """
            return html.Li(
                html.A(
                    children=headline,
                    href=href,
                    target='_blank',
                    rel='noopener noreferrer'
                ),
                style={
                    'margin-bottom': '10px'
                }
            )

        # if the refresh button was not clicked, do nothing
        if n_clicks is None:
            raise PreventUpdate
        
        # how many headlines we want to display
        MAX_HEADLINES = 10
        
        # get the MAX_HEADLINES newest headlines
        engine, session = autoconnect_db()
        reports = session.query(Report).order_by(Report.timestamp.desc()).limit(MAX_HEADLINES).all()

        # build the headlines list
        headlines = []

        for report in reports:

            # get report properties
            report_title = report.title
            report_link = report.link
            report_date = report.timestamp.strftime('%d.%m.%Y')

            # add the date to the title
            report_title += f' ({report_date})'

            headlines.append(headline_to_li(report_title, report_link))            
        
        return headlines
        



