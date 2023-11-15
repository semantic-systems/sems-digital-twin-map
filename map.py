from tqdm import tqdm
import branca.colormap as cm

from dash import Dash, html
import dash_leaflet as dl

# database imports
from sqlalchemy import func
from shapely.geometry import mapping
from shapely.wkb import loads

# data models
from database import Base, Feature, FeatureSet, Style, Colormap, connect_db

def style_to_dict(style):
    """
    Convert a Style from the database to a dictionary that can be used by dash-leaflet
    """
    style_dict = {
        'color': style.color,
        'fillColor': style.fill_color,
        'weight': style.line_weight
    }

    return style_dict

# get a features lat and long
def get_lat_long(feature, session):
    """
    Get the latitude and longitude of a feature, if its geometry type is 'Point'
    returns a tuple of (lat, long)
    """

    assert feature.geometry_type == 'Point', 'Features geometry_type be "Point"'

    geometry = feature.geometry

    x, y = session.query(func.ST_X(Feature.geometry), func.ST_Y(Feature.geometry)).filter(Feature.id == feature.id).first()
    position = (y, x)

    return position

def create_marker(feature, style=None, popup=None) -> dl.Marker:
    """
    Create a dash-leaflet Marker from a feature.
    Don't use this, use create_awesome_marker() instead (much cooler)
    """

    position = get_lat_long(feature)

    children = []

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

def create_geojson(feature, style=None, popup=None) -> dl.GeoJSON:
    """
    Create a dash-leaflet GeoJSON object from a feature.
    """

    children = []

    if popup is not None:
        children.append(dl.Popup(content=popup))
    
    if style is not None:
        style_dict = style_to_dict(style)

    return dl.GeoJSON(
        data=feature,
        style=style_dict,
        children=children
        )

def feature_to_geojson(feature):
    """
    Convert a Feature from the database to a GeoJSON Feature object
    """

    properties = feature.properties
    geometry_type = feature.geometry_type
    feature_set = feature.feature_set

    raw_geometry = feature.geometry.data
    shape_geometry = loads(bytes(raw_geometry))
    geojson_geometry = mapping(shape_geometry)

    geojson =  {
        "type": "Feature",
        "geometry": geojson_geometry,
        "properties": properties
    }

    return geojson

# david is a god for making this work
def create_awesome_marker(position=(0.0,0.0), style=None, popup=None, icon='circle', color='red') -> dl.DivMarker:
    """
    Create an awesome marker with a Font Awesome icon
    - feature: Feature from the database
    - style: Style from the database
    - popup: Popup html content as string
    - icon: Font Awesome icon name from fontawesome
    - color: marker color as string. see lma.css for possible values (default: red)
    """

    children = []

    if style is not None:
        icon = style.icon_name
        icon_prefix = style.icon_prefix # currently unused
        color = style.color

    if popup is not None:
        children.append(dl.Popup(content=popup))

    awesome_marker = dl.DivMarker(
        position=position,
        children=children,
        iconOptions=dict(
            html=f'<i class="awesome-marker awesome-marker-icon-{color} leaflet-zoom-animated leaflet-interactive"></i>'
            f'<i class="fa fa-{icon} icon-white" aria-hidden="true" style="left: 1px !important;position: fixed;top: 2px; scale:120%;"></i>',
            className='custom-div-icon',
            iconSize=[20, 20],
            iconAnchor=[10, 30],
            tooltipAnchor=[10, -20],
            popupAnchor=[-3, -31]
        )
    )

    return awesome_marker


def create_dash():
    """
    Creates a dash app. Also adds external stylesheets and scripts.
    """
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

    app.layout = html.Div([
    dl.Map(
        [
            dl.LayersControl(
                [
                    dl.BaseLayer(
                        dl.TileLayer(
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                        ),
                        name='OpenStreetMap',
                        checked=True,
                        )
                ],
                id='layer_control'
            )
        ],
        zoom=12,
        center=(53.55, 9.99),
        style={'width': '1000px', 'height': '500px'})
])

    return app

# build the map
def build_map(session, verbose=False):

    if verbose: print("================")
    if verbose: print("Building the map")
    if verbose: print("================")

    if verbose: print("Creating the dash app...  ", end='')
    app = create_dash()
    if verbose: print("Done!")

    # get all feature_sets
    # feature_sets = session.query(FeatureSet).all()
    if verbose: print("Getting all FeatureSets... ", end='')
    feature_sets = session.query(FeatureSet).filter(FeatureSet.name != "Straße").all()  # exclude Straße, very big dataset
    if verbose: print("Done!")

    # get the layers control
    layers_control = app.layout.children[0].children[0]

    if verbose: print("Building the map...        ", end='')

    for feature_set in tqdm(feature_sets):

        # get the features and style for this feature set
        features = feature_set.features
        style = feature_set.style

        if style is None:
            if verbose: print("No style for feature set " + feature_set.name + ". Skipping...")
            continue

        # save all map objects of this feature_set in here
        layer_group_children = []

        # get the popup properties of this feature
        popup_properties = style.popup_properties

        for feature in features:

            # get the properties for the popup
            popup_content = f"<b>{feature_set.name}</b><br>"

            for property in popup_properties:
                current_property = popup_properties[property]
                value = feature.properties.get(current_property, '')
                popup_content += f"<b>{property}</b>: {value}<br>"

            geometry_type = feature.geometry_type

            if geometry_type == "Point":

                # old and boring markers
                # marker = create_marker(feature, style, popup=popup_content)

                # new and cool markers
                (lat, long) = get_lat_long(feature, session)

                icon = style.icon_name
                color = style.color

                marker = create_awesome_marker(position=(lat, long), icon=icon, color=color, popup=popup_content)
                layer_group_children.append(marker)

            else:

                # create a geojson map object, shows a polygon
                geojson_dict = feature_to_geojson(feature)
                geojson = create_geojson(geojson_dict, style, popup=popup_content)
                layer_group_children.append(geojson)

        # create a layer group for this feature set
        layer_group = dl.LayerGroup(children=layer_group_children, id=feature_set.name)
        overlay = dl.Overlay(layer_group, name=feature_set.name)
        layers_control.children.append(overlay)

    if verbose: print("================")
    if verbose: print("   Map built!   ")
    if verbose: print("================")

    return app