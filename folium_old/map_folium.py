import folium
from folium.plugins import MarkerCluster
from tqdm import tqdm
import branca.colormap as cm

# database imports
from sqlalchemy import func
from shapely.geometry import mapping
from shapely.wkb import loads

# data models
from database import Base, Feature, FeatureSet, Style, Colormap, connect_db

# GeoJson objecs will be styled like this
def create_style_function(style):
    def style_function(feature):

        # Default color from style settings
        fillColor = style.fill_color
        color = style.color
        line_weight = style.line_weight

        # if there is a colormap, use it
        if style.colormap:

            # get the colormap information
            colormap = style.colormap
            min_color, max_color = colormap.min_color, colormap.max_color
            min_value, max_value = colormap.min_value, colormap.max_value
            colormap_property = colormap.property

            # get the value from the features property
            # if it doesnt exist, use the minimum value color
            feature_properties = feature.get('properties', {})
            property_value = feature_properties.get(colormap_property, colormap.min_value)

            # build the colormap
            # this uses a branca.colormap.LinearColormap
            linear_colormap = cm.LinearColormap(
                colors=[min_color, max_color],
                vmin=min_value,
                vmax=max_value,
            )

            # set the color
            fillColor = linear_colormap(property_value)[:7]
            color = fillColor
        
        # add more values here if needed
        # see https://leafletjs.com/reference.html#path-option
        return {
            'fillColor': fillColor,
            'color': color,
            'weight': line_weight
        }
    
    return style_function

# build the map
def build_map(session, verbose=False):

    if verbose: print("================")
    if verbose: print("Building the map")
    if verbose: print("================")

    if verbose: print("Creating a folium.Map object... ", end='')
    m = folium.Map(location=(53.55, 9.99), zoom_start=12)
    if verbose: print("Done!")

    # get all feature_sets
    # feature_sets = session.query(FeatureSet).all()
    if verbose: print("Querying the database... ", end='')
    feature_sets = session.query(FeatureSet).filter(FeatureSet.name != "Straße").all()  # exclude Straße, very big dataset
    if verbose: print("Done!")

    # iterate over all feature_sets
    for feature_set in tqdm(feature_sets, disable=not verbose):
        
        # Create a FeatureGroup for this set of features
        feature_group = folium.FeatureGroup(name=feature_set.name, show=False)

        # get the style of this feature
        style = feature_set.style

        # only display if there is a style for this feature
        if style == None:
            continue

        # get the popup properties of this feature
        popup_properties = style.popup_properties
        
        # iterate over all features in the feature_set
        for feature in feature_set.features:

            # get the style function
            style_function = create_style_function(style)
            
            # build the popup window
            popup_content = f"<b>{feature_set.name}</b><br>"

            for property in popup_properties:
                current_property = popup_properties[property]
                value = feature.properties.get(current_property, '')
                popup_content += f"<b>{property}</b>: {value}<br>"
            
            geometry_type = feature.geometry_type

            # Create a Marker or a GeoJSON object depending on the geometry type
            if geometry_type.upper() == 'POINT':

                # Query the Point's geometry
                x, y = session.query(func.ST_X(Feature.geometry), func.ST_Y(Feature.geometry)).filter(Feature.id == feature.id).first()

                # get the icon information
                icon_prefix = style.icon_prefix
                icon_name = style.icon_name

                folium.Marker(
                    location=[y, x], # Note the switch, as folium expects [lat, lon]
                    popup=popup_content,
                    icon=folium.Icon(icon=icon_name, prefix=icon_prefix, color=style.color),
                    show=False
                ).add_to(feature_group)

            else:

                # Convert the geometry to a format folium can read
                shape_geometry = loads(bytes(feature.geometry.data))
                geojson_geometry = mapping(shape_geometry)

                geojson_feature = {
                    'type': 'Feature',
                    'properties': feature.properties,
                    'geometry': geojson_geometry
                }

                folium.GeoJson(
                    geojson_feature, 
                    style_function=style_function, 
                    tooltip=popup_content,
                    show=False
                ).add_to(feature_group)
                
        feature_group.add_to(m)

    folium.LayerControl().add_to(m)

    if verbose: print("================")
    if verbose: print("   Map built!")
    if verbose: print("================")

    return m