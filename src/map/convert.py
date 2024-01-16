import branca.colormap as cm
import dash_leaflet as dl

from sqlalchemy import func
from shapely.geometry import mapping
from shapely.wkb import loads

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap
from data.connect import autoconnect_db

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
    See the [leaflet docs](https://leafletjs.com/reference.html#path)
    This function is used specifically for features that have a colormap
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