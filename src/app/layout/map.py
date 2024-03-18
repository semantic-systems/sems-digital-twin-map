from datetime import date, timedelta, datetime
from datetime import datetime

from dash import Dash, html, dcc, Output, Input, State, callback_context
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

from sqlalchemy import inspect

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario
from data.connect import autoconnect_db
from data.build import build, refresh
from app.convert import layer_id_to_layer_group, scenario_id_to_layer_group

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
                )
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
        dcc.Store(id='event_range_full', data=[]),                 # the full event range, selected by event_range_picker
        dcc.Store(id='event_range_selected', data=[]),             # the selected event range, selected by slider_events
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
        This callback is triggered when the overlay_checklist changes.
        It updates the map children and the active_overlays_data.
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
        
        # delete all current layer groups (meaning, delete all existing markers and polygons)
        # TODO: this can be done more efficiently by only changing the layer groups, not rebuilding them from scratch
        # but i will warn you, it will cost you a lot of time and nerves (as it has me already)
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