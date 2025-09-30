from datetime import date, timedelta, datetime
from datetime import datetime
import json

from dash import Dash, html, dcc, Output, Input, State, callback_context, MATCH, ALL, ctx
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

from sqlalchemy import inspect

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario, Report
from data.connect import autoconnect_db
from data.build import build, refresh
from app.convert import layer_id_to_layer_group, scenario_id_to_layer_group, style_to_dict
from app.layout.map.sidebar import get_sidebar_content, get_sidebar_dropdown_platform_values, get_sidebar_dropdown_event_type_values
from app.layout.map.geocoder import geolocate, PREDICTED_LABELS
from server_reports import fetch_osm_polygon


# IMPORTANT NOTE
# in this branch, some components have been disabled
# you can reenable them by removing the 'display': 'none' from their style dictionary

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

    # pre-built the content of specific menu items
    # like the checkboxes of the layers or the values of the dropdowns in the reports menu
    layer_checkboxes = build_layer_checkboxes()
    scenario_checkboxes = build_scenario_checkboxes()
    reports_dropdown_platform = get_sidebar_dropdown_platform_values()
    reports_dropdown_event_type = get_sidebar_dropdown_event_type_values()

    layout_map = [
        dl.Map(
            children = [
                dl.TileLayer(
                    url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                    id='tile_layer_osm'
                ),
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
        html.Button(
            id='button_toggle_layers',
            children='-',
            style={
                'position': 'absolute',
                'float': 'right',
                'top': '0px',
                'right': '0',
                'margin': '10px',
                'z-index': '1001',
                'padding': '10px',
                'border': '1px solid #ccc',
                'width': '35px',
                'height': '35px'
            }
        ),
        html.Div(  # here we create a 'fake' layers control that looks identical to dash-leaflet, but gives us more control
            id='layers_control',
            children=[
                html.P(
                    children='Layers',
                    style={
                        'font-size': '14pt',
                        'font-weight': 'bold',
                        'margin': '4px 2px 4 2px',
                        'text-align': 'center',
                        'color': '#404040'
                    }
                ),
                dcc.Checklist(
                    id='overlay_checklist',
                    options=layer_checkboxes,
                    value=[]
                ),
                dcc.Tabs(
                    id='map-tabs',
                    children=[
                    dcc.Tab(
                        label='Scenarios',
                        children=[
                            dcc.Checklist(
                                id='scenario_checklist',
                                options=scenario_checkboxes,
                                value=[]
                            )
                        ]
                    )],
                    style={"display": "none"}
                ),
                html.Hr(
                    style={
                        'margin': '5px 4px 5px 4px',
                        'border': '0',
                        'border-bottom': '1px solid #777',
                        "display": "none"
                    }
                ),
                dcc.Checklist(
                    id='options_checklist',
                    options=[
                        {'label': 'Hide Features with Timestamp', 'value': 'hide_with_timestamp'},
                        {'label': 'Hide Features without Timestamp', 'value': 'hide_without_timestamp'},
                        {'label': 'Filter by Timestamp', 'value': 'filter_by_timestamp'}
                        ],
                    value=[],
                    style={"display": "none"}
                ),
                # special buttons, hidden for now from the end user
                # html.Div(
                #     children=[
                #         Hide the Rebuild button from the user
                #         html.Button(
                #             children="Rebuild",
                #             id="button_rebuild",
                #             style={
                #                 "padding": "10px 20px 10px 20px",
                #                 "margin": "5px"
                #             }
                #         ),
                #         html.Button(
                #             children="Refresh",
                #             id="button_refresh_items",
                #             className='button-common',
                #             style={
                #                 "padding": "10px 20px 10px 20px",
                #                 "margin": "5px"
                #             }
                #         ),
                #         html.Button(
                #             children="Update Menu",
                #             id="button_update_menu",
                #             className='button-common',
                #             style={
                #                 "padding": "10px 20px 10px 20px",
                #                 "margin": "5px"
                #             }
                #         )
                #     ],
                #     style={
                #         "display": "flex",
                #         "flex-wrap": "wrap",
                #         "justify-content": "center",
                #         "align-items": "center"
                #     }
                # ),
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
        html.Button(
            id='button_toggle_event_range',
            children='-',
            style={
                'position': 'absolute',
                'float': 'left',
                'bottom': '0px',
                'left': '0px',
                'margin': '10px',
                'z-index': '1001',
                'padding': '10px',
                'border': '1px solid #ccc',
                'width': '35px',
                'height': '35px',
                "display": "none"
            }
        ),
        html.Div(
            id='event_range',
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
                # 'display': 'flex',
                'align-items': 'center',
                'justify-content': 'space-between',
                'position': 'absolute',
                'left': '0',
                'right': '0',
                'bottom': '0',
                'margin': '10px',
                'background-color': 'white',
                'border': '1px solid #ccc',
                'padding': '10px 10px 10px 50px',
                'box-shadow': '0 2px 4px rgba(0,0,0,0.1)',
                'border-radius': '5px',
                'z-index': '1000',
                'color': '#333',
                "display": "none"
            }
        ),
        html.Button(
            id='button_toggle_reports',
            children='-',
            style={
                'position': 'absolute',
                'float': 'left',
                'top': '150px',
                'left': '0',
                'margin': '10px',
                'z-index': '1001',
                'padding': '10px',
                'border': '1px solid #ccc',
                'width': '35px',
                'height': '35px',
                "display": "none"
            }
        ),
        html.Div(
            id='div_reports',
            children=[
                html.P(
                    children='Reports',
                    style={
                        'font-size': '14pt',
                        'font-weight': 'bold',
                        'margin': '4px 2px 4 2px',
                        'text-align': 'center',
                        'color': '#404040'
                    }
                ),
                dcc.Dropdown(
                    options=reports_dropdown_platform,
                    id='reports_dropdown_platform',
                    optionHeight=20,
                    placeholder='Platform',
                    style={
                        "margin-bottom": "10px",
                        "font-size": "7.5pt"
                    }
                ),
                dcc.Dropdown(
                    options=reports_dropdown_event_type,
                    id='reports_dropdown_event_type',
                    optionHeight=20,
                    placeholder='Event Type',
                    style={
                        "margin-bottom": "10px",
                        "font-size": "7.5pt"
                    }
                ),
                html.Ul(
                    id='reports_list',
                    children=[],    # empty list, will be filled by the callback
                    style={
                        # increase child separator
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
                'min-height': '195px',
                'overflow-y': 'auto',
                'width': '250px',
                # "display": "none"
            }
        ),
        html.Button(
            id='button_toggle_geocoder',
            children='-',
            style={
                'position': 'absolute',
                'top': '290px',
                'right': '0px',
                'margin': '10px',
                'z-index': '1001',
                'padding': '10px',
                'border': '1px solid #ccc',
                'width': '35px',
                'height': '35px'
            }
        ),
        html.Div(
            id='div_geocoder',
            children=[
                html.P(
                    children='Geocoder',
                    style={
                        'font-size': '14pt',
                        'font-weight': 'bold',
                        'margin': '4px 2px 10px 2px',
                        'text-align': 'center',
                        'color': '#404040'
                    }
                ),
                dcc.Textarea(
                    id='geocoder_text_input',
                    placeholder='Enter place name or description...',
                    style={
                        'width': '236px',
                        'height': '60px',
                        'padding': '6px',
                        'font-size': '9pt',
                        'margin-bottom': '10px',
                        'border-radius': '4px',
                        'border': '1px solid #ccc'
                    }
                ),
                html.Button(
                    'Find',
                    id='geocoder_button',
                    n_clicks=0,
                    style={
                        'width': '100%',
                        'padding': '6px',
                        'font-size': '9pt',
                        'background-color': '#4CAF50',
                        'color': 'white',
                        'border': 'none',
                        'border-radius': '4px',
                        'cursor': 'pointer',
                        'margin-bottom': '10px'
                    }
                ),
                html.Hr(style={'margin': '5px 0'}),
                html.Div(id='geocoder_result_types', style={'font-size': '10pt', 'color': '#424242'}),
                html.Hr(style={'margin': '5px 0'}),
                dcc.Dropdown(
                    id='geocoder_entity_dropdown',
                    placeholder='Select location',
                        optionHeight=24,
                    style={
                        'width': '236px',
                        'height': '34px',
                        'font-size': '9pt',
                        'margin-bottom': '10px',
                        'display': 'none'
                    }
                ),
                html.Div(
                    id='geocoder_output',
                    children=[
                        html.Div(id='geocoder_result_description', style={'font-size': '9pt', 'margin-bottom': '5px', 'font-weight': 'bold', 'color': '#424242'}),
                        html.Div(id='geocoder_result_lat', style={'font-size': '9pt'}),
                        html.Div(id='geocoder_result_lon', style={'font-size': '9pt', 'margin-bottom': '5px'}),
                        html.A(id='geocoder_result_url', href='#', target='_blank', style={'font-size': '9pt', 'display': 'block'})
                    ]
                )
            ],
            style={
                'position': 'absolute',
                'float': 'right',
                'top': '350px',
                'right': '0px',
                'background-color': 'white',
                'border': '1px solid #ccc',
                'border-radius': '5px',
                'margin': '10px',
                'padding': '10px',
                'box-shadow': '0 2px 4px rgba(0,0,0,0.1)',
                'z-index': '1000',
                'width': '250px'
            }
        ),
        dcc.Store(id='event_range_full', data=[]),                 # the full event range, selected by event_range_picker
        dcc.Store(id='event_range_selected', data=[]),             # the selected event range, selected by slider_events
        dcc.Store(id='geocoder_types', data={}),                   # the types of events the geocoder found
        dcc.Store(id='geocoder_entities', data=[]),                # the geocoder entities, selected by geocoder_entity_dropdown
        dcc.Interval(id='interval_refresh_reports', interval=3600000 , n_intervals=0),  # refresh the reports every hour
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
            Output('map', 'children', allow_duplicate=True)
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
        ],
        prevent_initial_call=True
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
    @app.callback(
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
            raise PreventUpdate
        
        if n_clicks is None:
            raise PreventUpdate
        
        if all([n is None for n in n_clicks]):
            raise PreventUpdate

        # get the callback content, to get the trigger id
        # we use this id to find the correct database feature
        # and use that features hash to highlight all other features with the same hash
        ctx = callback_context

        if not ctx.triggered:
            raise PreventUpdate
        
        feature_hash = None
        
        for click_element in dbl_click_data:


            if click_element is None:
                continue

            feature_hash = click_element['properties']['hash']
            break

        if feature_hash is None:
            raise PreventUpdate

        # hide all features with a different hash
        map_children = highlight_events_predictions(feature_hash, map_children, hide_other=True)

        return map_children
    
    @app.callback(
        Output('geocoder_entity_dropdown', 'options'),
        Output('geocoder_entity_dropdown', 'value'),
        Output('geocoder_entity_dropdown', 'style'),
        Output('geocoder_entities', 'data'),
        Output('geocoder_types', 'data'),
        Input('geocoder_button', 'n_clicks'),
        State('geocoder_text_input', 'value'),
        prevent_initial_call=True
    )
    def geocode_text(n_clicks, text):

        if not n_clicks or not text:
            raise PreventUpdate

        result = geolocate(text)

        if result is None:
            # geolocation likely failed
            return [], None, {'display': 'none'}, []

        entities = result.get('geo_linked_entities', [])
        processed_entities = []
        for entity in entities:
            if isinstance(entity.get("location"), dict):
                osm_id = entity["location"]["osm_id"]
                osm_type = entity["location"]["osm_type"]
                polygon = fetch_osm_polygon(osm_type, osm_id)
                entity["location"]["polygon"] = polygon
                processed_entities.append(entity["location"])



        # no entities found
        if not processed_entities:
            return [], None, {'display': 'none'}, []

        opts = [{'label': e['name'], 'value': i} for i, e in enumerate(processed_entities)]

        # get the types of the events
        types = result.get('predicted_labels', [])

        return opts, 0, {'width': '250px', 'height': '34px', 'font-size': '9pt', 'margin-bottom': '10px', 'display': 'block'}, processed_entities, types


    def create_elements(loc, identifier: str):
        elements = []
        # POLYGON (preferred) or RECTANGLE (fallback)
        polygon_data = loc.get("polygon")
        bbox = loc.get("boundingbox", None)

        print(loc)

        if polygon_data and "coordinates" in polygon_data and len(polygon_data["coordinates"]) > 0:
            try:
                if polygon_data["type"] in {"Polygon", "MultiPolygon"}:
                    polygons = []
                    if polygon_data["type"] == "Polygon":
                        polygons = polygon_data["coordinates"]
                    elif polygon_data["type"] == "MultiPolygon":
                        polygons = polygon_data["coordinates"]

                    for part in polygons:
                        for ring in part:
                            polygon = dl.Polygon(
                                positions=[[lat, lon] for lon, lat in ring],
                                color="blue",
                                fill=True,
                                fillOpacity=0.15,
                                weight=2,
                                id=f'tmp_polygon_{identifier}'
                            )
                            elements.append(polygon)
                elif polygon_data["type"] in {"LineString", "MultiLineString"}:
                    lines = []
                    if polygon_data["type"] == "LineString":
                        lines = [polygon_data["coordinates"]]
                    elif polygon_data["type"] == "MultiLineString":
                        lines = polygon_data["coordinates"]

                    for line in lines:
                        polyline = dl.Polyline(
                            positions=[[lat, lon] for lon, lat in line],
                            color="#00008B",  # DarkBlue hex color
                            weight=6,  # Thicker line, default is usually 3
                            dashArray=None,  # solid line (remove dashes if you want solid)
                            id=f'tmp_line_{identifier}'
                        )
                        elements.append(polyline)
            except Exception as e:
                print(f"Polygon parse error: {e}")
        if not elements:
            if bbox and len(bbox) == 4:
                try:
                    min_lat, max_lat = float(bbox[0]), float(bbox[1])
                    min_lon, max_lon = float(bbox[2]), float(bbox[3])
                    rectangle = dl.Rectangle(
                        bounds=[
                            [min_lat, min_lon],  # SW
                            [max_lat, max_lon],  # NE
                        ],
                        color="blue",
                        fill=True,
                        fillOpacity=0.15,
                        weight=2,
                        id=f'tmp_rect_{identifier}'
                    )
                    elements.append(rectangle)
                except Exception as e:
                    print(f"Bounding box parse error: {e}")
        return elements

    def get_children(map_children):
        # Remove previous temp markers and rectangles
        children = [
            c for c in map_children
            if not (
                (isinstance(c["props"]["id"], str) and (
                        c["props"]["id"].startswith("tempmarker_") or
                        c["props"]["id"].startswith("tmp_rect_") or
                        c["props"]["id"].startswith("tmp_polygon_") or
                        c["props"]["id"].startswith("report_tmp_marker") or
                        c["props"]["id"].startswith("report_tmp_rect") or
                        c["props"]["id"].startswith("report_tmp_polygon") or
                        c["props"]["id"].startswith("tmp_line")
                ))
            )
        ]
        return children

    @app.callback(
        [
            Output('map', 'children', allow_duplicate=True),
            Output('map', 'viewport', allow_duplicate=True)
        ],
        [Input({'type': 'report-entry', 'index': ALL}, 'n_clicks')],
        State('map', 'children'),
        State({'type': 'report-entry', 'index': ALL}, 'id'),
        prevent_initial_call=True
    )
    def show_report_pins(report_nclicks, map_children, report_ids):
        if not ctx.triggered:
            raise PreventUpdate

        triggered = ctx.triggered[0]['prop_id']  # e.g. '{"type":"report-entry","index":123}.n_clicks'
        triggered_id_str = triggered.split('.')[0]
        if not triggered_id_str or triggered_id_str == '.':
            raise PreventUpdate
        triggered_id = json.loads(triggered_id_str)
        report_id = triggered_id.get('index')
        if report_id is None:
            raise PreventUpdate

        # Query the report
        engine, session = autoconnect_db()
        report = session.query(Report).filter(Report.id == report_id).first()
        session.close()
        engine.dispose()

        if not report:
            raise PreventUpdate

        locations = getattr(report, 'locations', None)
        if not locations or not isinstance(locations, list):
            raise PreventUpdate

        children = get_children(map_children)

        markers = []
        rectangles = []

        for i, loc in enumerate(locations):
            lat = loc.get('lat')
            lon = loc.get('lon')
            title = loc.get('name', loc.get("mention", "Unspecified"))
            desc = loc.get('display_name', '')
            lat_s = f'Latitude: {lat}'
            lon_s = f'Longitude: {lon}'
            url = f"https://www.openstreetmap.org/{loc['osm_type']}/{loc['osm_id']}"
            if lat is None or lon is None:
                continue

            # MARKER
            popup = dl.Popup(
                children=[
                    html.H4(title, style={'font-size': '12pt', 'color': '#424242', 'margin': '0 0 4px 0',
                                          'font-weight': 'bold'}),
                    html.P(desc, style={'font-size': '10pt', 'color': '#424242', 'margin': '2px 0'}),
                    html.P(lat_s, style={'font-size': '10pt', 'color': '#424242', 'margin': '2px 0'}),
                    html.P(lon_s, style={'font-size': '10pt', 'color': '#424242', 'margin': '2px 0'}),
                    html.A('Open in OSM', href=url, target='_blank', style={'font-size': '10pt', 'margin': '4px 0 0'})
                ],
                position=(lat, lon)
            )
            marker = dl.DivMarker(
                position=(lat, lon),
                children=[popup],
                iconOptions=dict(
                    html='<i class="awesome-marker awesome-marker-icon-blue leaflet-zoom-animated leaflet-interactive"></i>'
                         '<i class="fa fa-thumb-tack icon-white" aria-hidden="true" '
                         'style="position: relative; top: 33% !important; left: 37% !important; '
                         'transform: translate(-50%, -50%) scale(1.2);"></i>',
                    className='custom-div-icon',
                    iconSize=[20, 20], iconAnchor=[10, 30], tooltipAnchor=[10, -20], popupAnchor=[-3, -31]
                ),
                id=f'report_tmp_marker_{report_id}_{i}'
            )
            markers.append(marker)

            rectangles += create_elements(loc, identifier=title)


        if not markers:
            raise PreventUpdate

        children += rectangles + markers

        # Center/zoom map
        # Option 1: Center on first marker
        lat_first = locations[0].get('lat')
        lon_first = locations[0].get('lon')
        viewport = {
            'center': (lat_first, lon_first),
            'zoom': 13,
            'transition': 'flyTo',
            'options': {'duration': 0.5}
        }

        return children, viewport


    @app.callback(
        Output('geocoder_result_types', 'children'),
        Output('geocoder_result_description', 'children'),
        Output('geocoder_result_url', 'children'),
        Output('geocoder_result_url', 'href'),
        Output('geocoder_result_lat', 'children'),
        Output('geocoder_result_lon', 'children'),
        Output('map', 'viewport'),
        Output('map', 'children', allow_duplicate=True),
        Input('geocoder_entity_dropdown', 'value'),
        State('geocoder_entities', 'data'),
        State('geocoder_types', 'data'),
        State('map', 'children'),
        prevent_initial_call=True
    )
    def show_entities(sel, entities, types, children):

        if sel is None or not entities:
            raise PreventUpdate

        # sel holds the index of the selected entity in the dropdown
        sel = int(sel)

        # remove previous geocoder markers
        base = get_children(children)

        # build markers for every entity
        markers = []
        rectangles = []
        for i, e in enumerate(entities):
            lat = float(e['lat'])
            lon = float(e['lon'])
            title = e.get('name', '')
            lat_s = f'Latitude: {lat}'
            lon_s = f'Longitude: {lon}'
            url = f"https://www.openstreetmap.org/{e['osm_type']}/{e['osm_id']}"

            popup = dl.Popup(
                children=[
                    html.H4(title, style={'font-size': '12pt', 'color': '#424242', 'margin': '0 0 4px 0', 'font-weight': 'bold'}),
                    html.P(lat_s,  style={'font-size': '10pt', 'color': '#424242', 'margin': '2px 0'}),
                    html.P(lon_s,  style={'font-size': '10pt', 'color': '#424242', 'margin': '2px 0'}),
                    html.A('Open in OSM', href=url, target='_blank', style={'font-size': '10pt', 'margin': '4px 0 0'})
                ],
                position=(lat, lon)
            )

            marker = dl.DivMarker(
                position=(lat, lon),
                children=[popup],
                iconOptions=dict(
                    html=f'<i class="awesome-marker awesome-marker-icon-darkred leaflet-zoom-animated leaflet-interactive"></i>'
                        '<i class="fa fa-map-pin icon-white" aria-hidden="true" '
                        'style="position: relative; top: 33% !important; left: 37% !important; '
                        'transform: translate(-50%, -50%) scale(1.2);"></i>',
                    className='custom-div-icon',
                    iconSize=[20, 20], iconAnchor=[10, 30],
                    tooltipAnchor=[10, -20], popupAnchor=[-3, -31]
                ),
                id=f'tempmarker_{title}'
            )

            markers.append(marker)

            rectangles += create_elements(e, identifier=title)

        # set the event types in the widget
        type_children = []
        if len(types) == 0:
            type_children.append(html.P("No Events found", style={'font-weight': 'bold', 'font-size': '10pt', 'color': '#424242'}))

        else:
            type_children.append(html.P("Events:", style={'font-weight': 'bold', 'font-size': '10pt', 'color': '#424242', 'margin': '2px 0'}))
            for i, t in enumerate(types):

                # get the display name of the event
                display_name = PREDICTED_LABELS.get(t, '')

                type_children.append(
                    html.P(display_name,
                        style={
                            'font-size': '10pt',
                            'color': '#424242',
                            'margin': '2px 0'
                        }
                    )
                )

        # selected entity for sidebar + viewport
        sel_e = entities[sel]
        sel_lat = float(sel_e['lat'])
        sel_lon = float(sel_e['lon'])
        sel_desc = sel_e.get('name', '')
        sel_url = f"https://www.openstreetmap.org/{sel_e['osm_type']}/{sel_e['osm_id']}"

        new_children = base + markers + rectangles

        viewport = {
            'center': (sel_lat, sel_lon),
            'zoom': 13,
            'transition': 'flyTo',
            'options': {'duration': 0.5}
        }

        return type_children, sel_desc, sel_url, sel_url, f'Latitude: {sel_lat}', f'Longitude: {sel_lon}', viewport, new_children


    # update the reports
    @app.callback(
        Output('reports_list', 'children'),
        [Input('interval_refresh_reports', 'n_intervals'), Input('reports_dropdown_platform', 'value'), Input('reports_dropdown_event_type', 'value')],
    )
    def update_reports(n_clicks, filter_platform, filter_event_type):
        """
        This callback is triggered every hour.
        It updates the reports component with the newest posts and reports.
        """

        # if the refresh button was not clicked, do nothing
        if n_clicks is None:
            raise PreventUpdate
        
        sidebar_content = get_sidebar_content(filter_platform=filter_platform, filter_event_type=filter_event_type)

        return sidebar_content
    
    @app.callback(
        Output('reports_dropdown_platform', 'options'),
        [Input('interval_refresh_reports', 'n_intervals')],
    )
    def update_report_dropdown_platform(n_clicks):
        """
        This callback is triggered every hour.
        It updates the reports dropdown with all platforms of the current data.
        """

        dropdown_platform_values = get_sidebar_dropdown_platform_values()

        return dropdown_platform_values

    @app.callback(
        Output('reports_dropdown_event_type', 'options'),
        [Input('interval_refresh_reports', 'n_intervals')],
    )
    def update_report_dropdown_event_type(n_clicks):
        """
        This callback is triggered every hour.
        It updates the reports dropdown with all classes of the current data.
        """

        dropdown_class_values = get_sidebar_dropdown_event_type_values()

        return dropdown_class_values

    
    # toggle the layers widget
    @app.callback(
        [Output('layers_control', 'style'), Output('button_toggle_layers', 'children')],
        [Input('button_toggle_layers', 'n_clicks')],
        [State('layers_control', 'style')],
        prevent_initial_call=True
    )
    def toggle_visibility_layers(n_clicks, overlay_checklist_style):
        """
        This callback is triggered when the toggle layers button is clicked.
        It toggles the visibility of the layers list.
        """
        
        # on  odd clicks, hide
        # on even clicks, show
        if n_clicks % 2 == 1:
            overlay_checklist_style['display'] = 'none'
            return [overlay_checklist_style, '+']
        else:
            overlay_checklist_style['display'] = 'block'
            return [overlay_checklist_style, '-']
    
    # toggle the reports widget
    @app.callback(
        [Output('div_reports', 'style'), Output('button_toggle_reports', 'children')],
        [Input('button_toggle_reports', 'n_clicks')],
        [State('div_reports', 'style')],
        prevent_initial_call=True
    )
    def toggle_visibility_reports(n_clicks, reports_headlines_style):
        """
        This callback is triggered when the toggle reports button is clicked.
        It toggles the visibility of the reports widget.
        """

        # if the toggle button was not clicked, do nothing
        if n_clicks is None:
            raise PreventUpdate
        
        # on  odd clicks, hide
        # on even clicks, show
        if n_clicks % 2 == 1:
            reports_headlines_style['display'] = 'none'
            return [reports_headlines_style, '+']
        else:
            reports_headlines_style['display'] = 'block'
            return [reports_headlines_style, '-']
    
    # toggle the event range widget
    @app.callback(
        [Output('event_range', 'style'), Output('button_toggle_event_range', 'children')],
        [Input('button_toggle_event_range', 'n_clicks')],
        [State('event_range', 'style')],
        prevent_initial_call=True
    )
    def toggle_visibility_event_range(n_clicks, event_range_style):
        """
        This callback is triggered when the toggle event range button is clicked.
        It toggles the visibility of the event range widget.
        """

        # if the toggle button was not clicked, do nothing
        if n_clicks is None:
            raise PreventUpdate
        
        # on  odd clicks, hide
        # on even clicks, show
        if n_clicks % 2 == 1:
            event_range_style['display'] = 'none'
            return [event_range_style, '+']
        else:
            event_range_style['display'] = 'flex'
            return [event_range_style, '-']

    @app.callback(
        [Output('div_geocoder', 'style'), Output('button_toggle_geocoder', 'children')],
        [Input('button_toggle_geocoder', 'n_clicks')],
        [State('div_geocoder', 'style')],
        prevent_initial_call=True
    )
    def toggle_visibility_geocoder(n_clicks, geocoder_style):
        """
        This callback toggles the visibility of the Geocoder widget.
        """
        if n_clicks % 2 == 1:
            geocoder_style['display'] = 'none'
            return [geocoder_style, '+']
        else:
            geocoder_style['display'] = 'block'
            return [geocoder_style, '-']




