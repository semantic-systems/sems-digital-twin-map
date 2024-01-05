from tqdm import tqdm
import branca.colormap as cm
from datetime import date, timedelta, datetime
from datetime import datetime

from dash import Dash, html, dcc, Output, Input, State, callback
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

# database imports
from sqlalchemy import func
from shapely.geometry import mapping
from shapely.wkb import loads

# data models
from database import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, autoconnect_db

# update the database
from build import api_to_db, refresh

def style_to_dict(style: Style) -> dict:
    """
    Convert a Style from the database to a dictionary that can be used by dash-leaflet.
    See the [leaflet docs](https://leafletjs.com/reference.html#path)
    """

    style_dict = {
        'borderColor': style.border_color,
        'areaColor': style.area_color,
        'weight': style.line_weight,
        'stroke': style.stroke,
        'opacity': style.opacity,
        'lineCap': style.line_cap,
        'lineJoin': style.line_join,
        'dashArray': style.dash_array,
        'dashOffset': style.dash_offset,
        'fill': style.fill, #boolean
        'fillColor': style.area_color, #same thing as borderColor?
        'color': style.border_color,
        'fillOpacity': style.fill_opacity,
        'fillRule': style.fill_rule
    }

    return style_dict

def style_to_dict_colormap(style: Style, feature: Feature) -> dict:
    """
    Convert a Style from the database to a dictionary that can be used by dash-leaflet.
    This function is used for features that have a colormap
    """

    style_dict_base = style_to_dict(style)

    # get the colormap
    colormap = style.colormap
    colormap_property = colormap.property
    colormap_min_value = colormap.min_value
    colormap_max_value = colormap.max_value
    colormap_min_color = colormap.min_color
    colormap_max_color = colormap.max_color

    # get the value of the colormap property
    properties = feature.properties
    colormap_value = properties.get(colormap_property, 0)

    # create the colormap
    colormap = cm.LinearColormap(
        [colormap_min_color, colormap_max_color],
        vmin=colormap_min_value,
        vmax=colormap_max_value
    )

    # get the color from the colormap
    colormap_color = colormap.rgb_hex_str(colormap_value)

    # add the colormap color to the style dict
    style_dict_base['color'] = colormap_color
    style_dict_base['fillColor'] = colormap_color

    return style_dict_base

def get_lat_long(feature: Feature) -> tuple:
    """
    Get the latitude and longitude of a feature, if its geometry type is 'Point' or 'MultiPoint'
    returns a tuple of (lat, long)
    """

    assert feature.geometry_type in ['Point', 'MultiPoint'], 'Features geometry_type must be "Point" or "MultiPoint"'

    # save the coordinates in here
    coordinates = []

    geometry = feature.geometry
    geometry_type = feature.geometry_type
    shapely_geometry = loads(bytes(geometry.data), hex=True)

    if geometry_type == 'Point':
        coordinate = (shapely_geometry.y, shapely_geometry.x)
        coordinates.append(coordinate)
    
    if geometry_type == 'MultiPoint':
        print(shapely_geometry)
        for point in shapely_geometry.geoms:
            coordinate = (point.y, point.x)
            coordinates.append(coordinate)

    return coordinates

def create_marker(feature: Feature, popup=None) -> dl.Marker:
    """
    Create a simple dash-leaflet Marker from a feature.
    Don't use this, use create_awesome_marker() instead (much cooler)
    """

    position = get_lat_long(feature)

    children = []

    # get the style of the feature
    style = feature.feature_set.style

    if style is not None:
        icon = style.icon_name
        color = style.color

    if popup is not None:
        children.append(dl.Popup(content=popup))

    marker = dl.Marker(
        position=position,
        children=children
        )

    return marker

def create_geojson(feature: Feature, popup=None) -> dl.GeoJSON:
    """
    Create a dash-leaflet GeoJSON object from a database Feature.
    """

    properties = feature.properties
    geometry_type = feature.geometry_type
    feature_set = feature.feature_set
    style = feature_set.style

    # create a geojson dict from the feature
    raw_geometry = feature.geometry.data
    shape_geometry = loads(bytes(raw_geometry))
    geojson_geometry = mapping(shape_geometry)

    geojson_dict =  {
        "type": "Feature",
        "geometry": geojson_geometry,
        "properties": properties
    }

    # create the dl.GeoJSON object
    children = []

    # build the popup window
    if popup is not None:
        children.append(dl.Popup(content=popup))
    
    # build the style dict
    if style is not None:
        if style.colormap is not None:  
            # if the style has a colormap, use the colormap style
            style_dict = style_to_dict_colormap(style, feature)
        else:                           
            # otherwise use the normal style
            style_dict = style_to_dict(style)
    
    geojson = dl.GeoJSON(
        data=geojson_dict,
        style=style_dict,
        children=children,
        id=f'geojson-{feature.id}'
    )

    return geojson

# david is a god for making this work
def create_awesome_marker(feature: Feature, popup=None) -> dl.DivMarker:
    """
    Create an awesome marker with a Font Awesome icon
    - feature: Feature from the database
    - style: Style from the database
    - popup: Popup html content as string
    - icon: Font Awesome icon name from https://fontawesome.com/icons
    - color: marker color as string. Possible values: ```{red, darkred, lightred, orange, beige, green, darkgreen,
    lightgreen, blue, darkblue, lightblue, purple, darkpurple, pink, cadetblue, white, gray, lightgray, black}```
    """

    # get all coordinates of the feature
    # if Point -> one coordinate
    # if MultiPoint -> multiple coordinates
    coordinates = get_lat_long(feature)

    style = feature.feature_set.style

    children = []

    if style is not None:
        marker_icon = style.marker_icon
        marker_color = style.marker_color

    if popup is not None:
        children.append(dl.Popup(content=popup))

    for coordinate in coordinates:

        awesome_marker = dl.DivMarker(
            position=coordinate,
            children=children,
            iconOptions=dict(
                html=f'<i class="awesome-marker awesome-marker-icon-{marker_color} leaflet-zoom-animated leaflet-interactive"></i>'
                f'<i class="fa fa-{marker_icon} icon-white" aria-hidden="true" style="position: relative; top: 33% !important; left: 37% !important; transform: translate(-50%, -50%) scale(1.2);"></i>',
                className='custom-div-icon',
                iconSize=[20, 20],
                iconAnchor=[10, 30],
                tooltipAnchor=[10, -20],
                popupAnchor=[-3, -31]
            ),
            id=f'marker-{id}'
        )

    return awesome_marker

def feature_to_map_object(feature: Feature, popup=None):
    """
    Takes in a Feature from the database and returns a dash-leaflet object.
    Returns an awesome marker or a GeoJSON object, based on its geometry_type
    """

    geometry_type = feature.geometry_type

    # if the geometry type is a point or multiple points, create markers
    # otherwise create a geojson object
    if geometry_type in ['Point', 'MultiPoint']:
        map_object = create_awesome_marker(feature, popup=popup)

    else:
        map_object = create_geojson(feature, popup=popup)

    return map_object

def feature_set_to_map_objects(feature_set: FeatureSet) -> list:
    """
    Takes in a FeatureSet from the database and returns a list of dash-leaflet objects.
    that contains all AwesomeMarkers or GeoJSON objects of the FeatureSet
    """

    map_objects = []

    # get the popup properties of this feature
    style = feature_set.style
    popup_properties = style.popup_properties

    for feature in feature_set.features:

        properties = feature.properties
            
        # build the popup window
        popup_content = f"<b>{feature_set.name}</b><br>"

        if popup_properties is not None:

            for property in popup_properties:
                current_property = popup_properties[property]
                value = properties.get(current_property, '')
                popup_content += f"<b>{property}</b>: {value}<br>"
    
        map_object = feature_to_map_object(feature, popup_content)
        map_objects.append(map_object)

    return map_objects

def overlay_id_to_layer_group(overlay_id) -> dl.LayerGroup:
    """
    Takes in an overlay_id and returns the corresponding layer group.
    This is a wrapper for collection_to_map_objects()
    """

    engine, session = autoconnect_db()

    # get the layer with the given id
    layer = session.query(Layer).get(overlay_id)
    feature_sets = layer.feature_sets

    map_objects = []

    for feature_set in feature_sets:
        # build the layer group for this collections
        map_objects.extend(feature_set_to_map_objects(feature_set))

    # close database connection
    session.close()
    engine.dispose()

    # create the layer group
    layer_group = dl.LayerGroup(
        children=map_objects,
        id=f'layergroup-{overlay_id}'
    )

    return layer_group

app = Dash(
    __name__,
    external_stylesheets=[
        'https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css',
        'http://code.ionicframework.com/ionicons/1.5.2/css/ionicons.min.css',
        'https://raw.githubusercontent.com/lennardv2/Leaflet.awesome-markers/2.0/develop/dist/leaflet.awesome-markers.css',
        'https://getbootstrap.com/1.0.0/assets/css/bootstrap-1.0.0.min.css',
    ],
    external_scripts=[
        'http://cdn.leafletjs.com/leaflet-0.6.4/leaflet.js',
        'https://kit.fontawesome.com/5ae05e6c33.js'
    ]
)

# get all available layers sets
engine, session = autoconnect_db()
layers = session.query(Layer).all()

# close database connection
session.close()
engine.dispose()

# create the map layout
app.layout = html.Div([
        dl.Map(
            [
                dl.TileLayer(
                    url='https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/de_basemapde_web_raster_farbe/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png',
                    attribution='&copy; <a href="https://basemap.de/">basemap.de</a>',
                    id='tile_layer'
                )
            ],
            zoom=12,
            center=(53.55, 9.99),
            style={
                'width': '100vw', 
                'height': '100vh',
                'display': 'inline-block',
                'position': 'relative',
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
                            children="Reload Datasets",
                            id="button_reload_datasets",
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
                    options=[{'label': layer.name, 'value': layer.id} for layer in layers],
                    value=[]
                ),
                html.Hr(
                    style={
                        'margin': '5px 4px 5px 4px',
                        'border': '0',
                        'border-bottom': '1px solid #777'
                    }
                ),
                dcc.Checklist(
                    id='event_visibility_checklist',
                    options=[
                        {'label': 'Show Events', 'value': 'show_events'},
                        {'label': 'Show Predictions', 'value': 'show_predictions'}
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
                'top': '0',
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
    ],
    style={'display': 'flex', 'flex-wrap': 'wrap'}
    )

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
@app.callback(
    [Output('dummy_output_1', 'children')],
    [Input('button_reload_datasets', 'n_clicks')]
)
def reload_datasets(n_clicks):
    """
    This callback is triggered when the reload button is clicked.
    It calls the api_to_db() function from build.py to update the database.
    """

    # if the reload button was not clicked, do nothing
    if n_clicks is None:
        raise PreventUpdate
    
    engine, session = autoconnect_db()

    # call the reload function
    api_to_db(session, refresh=False, verbose=True)

    # close database connection
    session.close()
    engine.dispose()

    raise PreventUpdate

    # return nothing
    return []

# call api to refresh the database
@app.callback(
    [Output('dummy_output_2', 'children')],
    [Input('button_refresh_items', 'n_clicks')]
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

# returns the app object for use in main.py
def get_app() -> Dash:
    """
    Returns the dash app object
    """
    return app