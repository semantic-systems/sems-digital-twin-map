from dash import Dash, html, dcc, Output, Input, State, callback, callback_context
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

from sqlalchemy import inspect
import requests
import json

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario
from data.connect import autoconnect_db
from data.build import get_default_style, feature_to_obj


def build_layout_text_geolocation():
    """
    Returns the layout for the text geolocation tab. Callbacks need to be configured separately.
    """

    layout = html.Div([

        # Page Header
        html.Div([
            html.H1("Text Geolocation", style={
                'font-family': 'Segoe UI, sans-serif',
                'margin-bottom': '5px',
                'color': '#222'
            }),
            html.P("Enter natural language text referring to a place. The system will attempt to extract and geolocate it.", style={
                'font-family': 'Segoe UI, sans-serif',
                'color': '#555',
                'margin-bottom': '0'
            })
        ], style={
            'padding': '20px 40px 10px 40px',
            'border-bottom': '1px solid #eee',
            'backgroundColor': '#fafafa'
        }),

        # Input Section
        html.Div([
            html.Div([
                dcc.Textarea(
                    id='text-geolocation-textarea',
                    placeholder="I took a walk through Jungfernstieg before heading to the Alster...",
                    style={
                        'width': '100%',
                        'height': '200px',
                        'padding': '15px',
                        'borderRadius': '10px',
                        'border': '1px solid #ccc',
                        'fontSize': '16px',
                        'fontFamily': 'Segoe UI, sans-serif',
                        'boxShadow': 'inset 0 1px 3px rgba(0,0,0,0.1)'
                    }
                ),
                html.Button('Geolocate', id='text-geolocation-button', n_clicks=0, style={
                    'marginTop': '15px',
                    'padding': '10px 20px',
                    'borderRadius': '8px',
                    'border': 'none',
                    'backgroundColor': '#4CAF50',
                    'color': 'white',
                    'fontWeight': 'bold',
                    'fontSize': '16px',
                    'cursor': 'pointer',
                    'boxShadow': '0 2px 5px rgba(0,0,0,0.1)'
                })
            ], style={
                'padding': '30px 40px 0px 40px',
                'maxWidth': '800px',
                'margin': 'auto'
            })
        ]),

        html.Div([
            html.Div([
                # Left: location info
                html.Div([
                    html.H3("Jungfernstieg", id='text-geolocation-title', style={'margin-bottom': '5px'}),
                    html.A("https://www.wikidata.org/wiki/Q322276",
                        href="https://www.wikidata.org/wiki/Q322276",
                        target="_blank",
                        id='text-geolocation-wikidata-link',
                        style={'display': 'block', 'margin-bottom': '15px'}),
                    html.Div("Railway station in germany.", id='text-geolocation-description', style={'margin-bottom': '15px'}),
                    html.Div("Latitude: 53.553611", id='text-geolocation-lat', style={'margin-top': '5px'}),
                    html.Div("Longitude: 9.9925", id='text-geolocation-lon')
                ], style={
                    'flex': '1',
                    'padding': '20px',
                    'font-family': 'Segoe UI, sans-serif',
                    'color': '#333'
                }),

                # Right: map
                html.Div([
                    dl.Map(
                        children=[
                            dl.TileLayer(
                                url='https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/de_basemapde_web_raster_farbe/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png',
                                attribution='&copy; <a href="https://basemap.de/">basemap.de</a>',
                                id='text-geolocation-tile-layer'
                            )
                        ],
                        zoom=12,
                        scrollWheelZoom=True,
                        touchZoom=True,
                        zoomControl=True,
                        doubleClickZoom=False,
                        center=(53.5511, 9.9937),
                        id='text-geolocation-map',
                        style={'width': '100%', 'height': '400px', 'borderRadius': '12px', 'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'}
                    )
                ], style={'flex': '1.2', 'padding': '20px'})
            ], style={
                'display': 'flex',
                'flexDirection': 'row',
                'justifyContent': 'space-between',
                'alignItems': 'flex-start',
                'gap': '20px',
                'backgroundColor': '#f9f9f9',
                'border': '1px solid #ddd',
                'borderRadius': '12px',
                'boxShadow': '0 4px 12px rgba(0, 0, 0, 0.05)',
                'margin': '30px 40px',
                'padding': '10px'
            })
        ])
    ])

    return layout

def callbacks_text_geolocation(app):

    @app.callback(
        Output('text-geolocation-title', 'children'),
        Output('text-geolocation-description', 'children'),
        Output('text-geolocation-wikidata-link', 'children'),
        Output('text-geolocation-wikidata-link', 'href'),
        Output('text-geolocation-lat', 'children'),
        Output('text-geolocation-lon', 'children'),
        Output('text-geolocation-map', 'viewport'),   # for flying to the coordinates
        Output('text-geolocation-map', 'children'),   # for adding the marker to the map
        Input('text-geolocation-button', 'n_clicks'),
        State('text-geolocation-textarea', 'value'),
        State('text-geolocation-map', 'children'),    # to get the current map state (so we can keep the tile layer)
        prevent_initial_call=True
    )
    def update_table(button_n_clicks, text_value, map_children):

        if button_n_clicks is None or text_value is None:
            # if the button hasn't been clicked or the text is empty, do nothing
            raise PreventUpdate

        # get the QID from the text
        qid = text_value.strip()

        # get the coordinates from the QID
        title, description, lat, lon = geolocate(qid)

        # build the link to the Wikidata page
        if lat is None or lon is None:
            return title, description, 'https://www.wikidata.org/wiki/404', 'https://www.wikidata.org/wiki/404', 'Latitude: ?', 'Latitude: ?', {}, map_children
        
        # if we got here, we have a valid QID and coordinates
        wikidata_link = f"https://www.wikidata.org/wiki/{qid}"
        lat_str = f"Latitude: {lat}"
        lon_str = f"Longitude: {lon}"

        # this dict specifies the map viewport
        map_dict = {
            'center': (lat, lon),
            'zoom': 13,
            'transition': 'flyTo'
        }

        # remove all children that are NOT the tile layer
        tile_layer = map_children[0]  # the first child is the tile layer
        map_children = [tile_layer]

        # add the marker to the map
        marker = dl.Marker(position=(lat, lon), children=[
            dl.Popup(title),
            ]
        )
        map_children.append(marker)

        return title, description, wikidata_link, wikidata_link, lat_str, lon_str, map_dict, map_children

def geolocate(text: str):
    """
    In the future, this will hit the geolocation API and return the Wikidata ID.
    """

    # for now, just assume the text is a valid QID
    qid = text.strip()

    return get_coordinate_location(qid)

def get_coordinate_location(qid, lang='en'):
    """
    Retrieve the (latitude, longitude) coordinates for a Wikidata entity.

    Parameters:
        qid (str): The Wikidata QID (e.g. "Q6451").
        lang (str): Language code for the labels and descriptions (default is 'en').

    Returns:
        tuple: (title, latitude, longitude) if coordinates are present, else (title, None, None) if no coordinates are found. If an error occurs or no entry was found, returns (None, None, None).
    """

    base_url = "https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items"
    url = f"{base_url}/{qid}"

    try:
        response = requests.get(url, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        data = response.json()

        title = data.get("labels", {}).get(lang, "Not found")
        description = data.get("descriptions", {}).get(lang, "No description available")

        # capitalize the first letter of the description
        description = description.capitalize()

        coord_statements = data.get("statements", {}).get("P625", [])
        if not coord_statements:
            return title, description, None, None

        content = coord_statements[0].get("value", {}).get("content", {})
        lat = content.get("latitude", None)
        lon = content.get("longitude", None)

        return title, description, lat, lon

    except (requests.RequestException, ValueError, KeyError):
        return "Not found", "No description available", None, None