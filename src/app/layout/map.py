from datetime import date, timedelta, datetime
from datetime import datetime

from dash import Dash, html, dcc, Output, Input, State
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

from sqlalchemy import inspect

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario
from data.connect import autoconnect_db
from data.build import build, refresh
from app.convert import overlay_id_to_layer_group

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

def get_layout_map():
    """
    Returns the layout for the map app. Callbacks need to be configured separately.
    This gets set as the child of a dcc.Tab in the main app.
    """

    # build the layer checkboxes
    layer_checkboxes = build_layer_checkboxes()

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
        dcc.Store(id='active_overlays', data=[]),   # we store the active overlays in here
        html.Div(                                   # here we create a 'fake' layers control that looks identical to dash-leaflet, but gives us more control
            [
                html.Div(
                    children=[
                        html.Button(
                            children="Full Rebuild",
                            id="button_rebuild",
                            style={
                                "padding": "5px",
                                "margin": "5px"
                            }
                        ),
                        html.Button(
                            children="Refresh Items",
                            id="button_refresh_items",
                            style={
                                "padding": "5px",
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
                dcc.Checklist(
                    id='overlay_checklist',
                    options=layer_checkboxes,
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
        dcc.Store(id='event_range', data=[]),   # we store the event range in here
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
        html.Div(id='dummy_output_1', style={'display': 'none'}),  # for some reason callback functions always need an output, so we create a dummy output for functions that dont return anything
        html.Div(id='dummy_output_2', style={'display': 'none'})
    ]
    
    return layout_map

def callbacks_map(app: Dash):
    """
    Links the dash app with the necessary callbacks.
    Pass the Dash app as an argument.
    """

    # a new layer was selected or deselected
    @app.callback(
        [Output('map', 'children'), Output('active_overlays', 'data')],
        [Input('overlay_checklist', 'value')],
        [State('map', 'children'), State('active_overlays', 'data')]
    )
    def update_map(selected_overlays, map_children, active_overlays_data):
        """
        This callback is triggered when the overlay_checklist changes.
        It updates the map children and the active_overlays_data.
        """

        # first, divide the map children into layer groups and non-layer groups
        # we only want to manipulate the layer groups (map_children_layergroup)
        map_children_no_layergroup = []
        map_children_layergroup = []

        for child in map_children:

            id = child['props']['id']

            # check if the child is a layer group
            # layer groups have an id that starts with 'layergroup'
            if id.startswith('layergroup'):
                map_children_layergroup.append(child)
            else:
                map_children_no_layergroup.append(child)
        
        # compare selected_overlays with active_overlays_data
        # find out if an overlay was selected or deselected
        # if an overlay was selected, add it to the map
        # if an overlay was deselected, remove it from the map
        if selected_overlays != active_overlays_data:

            # get the overlay that was selected or deselected
            changed_overlay = list(set(selected_overlays) ^ set(active_overlays_data))[0]

            # check if the overlay was selected or deselected
            if changed_overlay in selected_overlays:
                # overlay was selected
                # add it to the map

                # get the layer group
                layer_group = overlay_id_to_layer_group(changed_overlay)

                # add the layer group to the map
                map_children_layergroup.append(layer_group)

            else:
                # overlay was deselected
                # remove it from the map

                # get the layer group id
                layer_group_id = f'layergroup-{changed_overlay}'

                # search for the layer group in the map children
                for child in map_children_layergroup:

                    # if the layer group was found, remove it from the map children
                    if child['props']['id'] == layer_group_id:
                        map_children_layergroup.remove(child)
        else:
            # no overlays were selected or deselected, do nothing
            # (this should never happen)
            raise PreventUpdate

        # update the active_overlays_data
        active_overlays_data = selected_overlays

        # combine the map children again
        new_map_children = map_children_no_layergroup + map_children_layergroup

        # return the updated map children and active_overlays_data
        return new_map_children, active_overlays_data

    # if a new event range was selected, update the event_range marks
    @app.callback(
        [Output('slider_events', 'marks'),
        Output('slider_events', 'min'),
        Output('slider_events', 'max'),
        Output('slider_events', 'value'),
        Output('event_range', 'data')], # Adding output for dcc.Store component
        [Input('event_range_picker', 'start_date'),
        Input('event_range_picker', 'end_date')],
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
        event_range_data = {'start_date': start_date_str, 'end_date': end_date_str}

        return slider_marks, min_value, max_value, slider_value, event_range_data

    @app.callback(
        [Output('event_range_text', 'children')],
        [Input('slider_events', 'value')],
        [State('event_range', 'data')]
    )
    def print_slider_value(value, event_range_data):
        """
        This callback is triggered when the slider value changes.
        It prints the current slider value to the console.
        """

        # If no event range data is available, raise PreventUpdate to stop the callback from firing
        if event_range_data is None:
            print("No event range data found. Stopping event range update.")
            raise PreventUpdate
        
        if type(event_range_data) == list:
            print("No event range data found. Stopping event range update.")
            raise PreventUpdate
        
        if value is None:
            print("No slider value available. Stopping event range update.")
            raise PreventUpdate
            
        # Convert string dates to datetime objects
        start_datetime = datetime.fromisoformat(event_range_data['start_date'])
        end_datetime = datetime.fromisoformat(event_range_data['end_date'])

        # Calculate the new start and end times based on the slider values
        new_start_datetime = start_datetime + timedelta(days=value[0])
        new_end_datetime = start_datetime + timedelta(days=value[1])

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
            
        ],

        return event_range_text

    # call function reload on button press
    # updates the layer checkboxes
    @app.long_callback(
        [Output('overlay_checklist', 'options'),],
        [Input('button_rebuild', 'n_clicks')],
        running=[
            (Output("button_rebuild", "disabled"), True, False),
            (Output("button_refresh_items", "disabled"), True, False),
        ],
    )
    def rebuild_database(n_clicks):
        """
        This callback is triggered when the reload button is clicked.
        It calls the build() function from src/data/build.py to update the database.
        """

        # if the reload button was not clicked, do nothing
        if n_clicks is None:
            raise PreventUpdate

        # call the build function
        build()

        # update the layer checkboxes
        layer_checkboxes = build_layer_checkboxes()

        # return the updated layer checkboxes
        return [layer_checkboxes]

    # call api to refresh the database
    @app.long_callback(
        [Output('dummy_output_2', 'children')],
        [Input('button_refresh_items', 'n_clicks')],
        running=[
            (Output("button_rebuild", "disabled"), True, False),
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