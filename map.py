from tqdm import tqdm
import branca.colormap as cm

from dash import Dash, html, dcc, Output, Input, State, callback
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

# database imports
from sqlalchemy import func
from shapely.geometry import mapping
from shapely.wkb import loads

# data models
from database import Base, Feature, FeatureSet, Layer, Style, Colormap, connect_db

def style_to_dict(style) -> dict:
    """
    Convert a Style from the database to a dictionary that can be used by dash-leaflet
    """

    style_dict = {
        'color': style.color,
        'fillColor': style.fill_color,
        'weight': style.line_weight,
    }

    return style_dict

def style_to_dict_colormap(style, feature) -> dict:
    """
    Convert a Style from the database to a dictionary that can be used by dash-leaflet
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

def get_lat_long(feature) -> tuple:
    """
    Get the latitude and longitude of a feature, if its geometry type is 'Point'
    returns a tuple of (lat, long)
    """

    assert feature.geometry_type == 'Point', 'Features geometry_type must be "Point"'

    geometry = feature.geometry
    shapely_geometry = loads(bytes(geometry.data), hex=True)

    longitude = shapely_geometry.x
    latitude = shapely_geometry.y

    return (latitude, longitude)

def create_marker(feature, popup=None) -> dl.Marker:
    """
    Create a simple dash-leaflet Marker from a feature.
    Don't use this, use create_awesome_marker() instead (much cooler)
    """

    position = get_lat_long(feature)

    children = []

    style = feature.feature_set.style

    if style is not None:
        icon = style.icon_name
        icon_prefix = style.icon_prefix
        color = style.color

    if popup is not None:
        children.append(dl.Popup(content=popup))

    marker = dl.Marker(
        position=position,
        children=children
        )

    return marker

def create_geojson(feature, popup=None) -> dl.GeoJSON:
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
def create_awesome_marker(feature, popup=None) -> dl.DivMarker:
    """
    Create an awesome marker with a Font Awesome icon
    - feature: Feature from the database
    - style: Style from the database
    - popup: Popup html content as string
    - icon: Font Awesome icon name from https://fontawesome.com/icons
    - color: marker color as string. Possible values: ```{red, darkred, lightred, orange, beige, green, darkgreen,
    lightgreen, blue, darkblue, lightblue, purple, darkpurple, pink, cadetblue, white, gray, lightgray, black}```
    """

    position = get_lat_long(feature)

    style = feature.feature_set.style

    children = []


    if style is not None:
        icon = style.icon_name
        icon_prefix = style.icon_prefix # currently unused, we only use fontawesome
        color = style.color

    if popup is not None:
        children.append(dl.Popup(content=popup))

    awesome_marker = dl.DivMarker(
        position=position,
        children=children,
        iconOptions=dict(
            html=f'<i class="awesome-marker awesome-marker-icon-{color} leaflet-zoom-animated leaflet-interactive"></i>'
            f'<i class="fa fa-{icon} icon-white" aria-hidden="true" style="position: relative; top: 33% !important; left: 37% !important; transform: translate(-50%, -50%) scale(1.2);"></i>',
            className='custom-div-icon',
            iconSize=[20, 20],
            iconAnchor=[10, 30],
            tooltipAnchor=[10, -20],
            popupAnchor=[-3, -31]
        ),
        id=f'marker-{id}'
    )

    return awesome_marker

def feature_to_map_object(feature, popup=None):
    """
    Takes in a Feature from the database and returns a dash-leaflet object.
    Either a awesome Marker or a GeoJSON object, based on its geometry_type
    """

    geometry_type = feature.geometry_type

    # if the geometry type is a point, create a marker
    # otherwise create a geojson object
    if geometry_type == 'Point':
        map_object = create_awesome_marker(feature, popup=popup)

    else:
        map_object = create_geojson(feature, popup=popup)

    return map_object

def feature_set_to_map_objects(feature_set) -> list:
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
    This is a wrapper for feature_set_to_layer_group()
    """

    engine, session = connect_db()

    # get the layer with the given id
    layer = session.query(Layer).get(overlay_id)
    feature_sets = layer.feature_set

    map_objects = []

    for feature_set in feature_sets:
        # build the layer group for this feature set
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
engine, session = connect_db()
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
                'position': 'relative'
                },
            id='map'
            ),
        dcc.Store(id='active_overlays', data=[]),   # we store the active overlays in here
        html.Div(                                   # here we create a 'fake' layers control that looks identical to dash-leaflet, but gives us more control
            dcc.Checklist(
                id='overlay_checklist',
                options=[{'label': layer.name, 'value': layer.id} for layer in layers],
                value=[]
            ),
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
    ],
    style={'display': 'flex', 'flex-wrap': 'wrap'}
    )

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

# returns the app object for use in main.py
def get_app() -> Dash:
    """
    Returns the dash app object
    """
    return app