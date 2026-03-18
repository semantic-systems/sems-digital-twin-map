import math
import os
import time
import requests
from datetime import date, timedelta, datetime, timezone
import json

import dash
from dash import Dash, html, dcc, Output, Input, State, callback_context, MATCH, ALL, ctx
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario, Report, UserReportState
from data.connect import autoconnect_db
from data.build import build, refresh
from app.convert import layer_id_to_layer_group, scenario_id_to_layer_group, style_to_dict
from app.layout.map.sidebar import get_sidebar_content, get_sidebar_dropdown_platform_values, get_sidebar_dropdown_event_type_values, get_sidebar_dropdown_relevance_type_values, ALL_EVENT_TYPES, ALL_RELEVANCE_TYPES, get_sidebar_max_timestamp
from app.i18n import t as _t, new_posts_label, TRANSLATIONS
from app.layout.map.geocoder import geolocate, PREDICTED_LABELS
from server_reports import fetch_osm_polygon


# IMPORTANT NOTE
# in this branch, some components have been disabled
# you can reenable them by removing the 'display': 'none' from their style dictionary

def build_layer_checkboxes(lang='de'):
    """
    Build the layer checkboxes for the layers control.
    Format: `[{'label': 'Layer Display Name', 'value': 'Layer ID'}]`
    """
    from app.i18n import layer_name as _layer_name

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

    layer_checkboxes = [{'label': _layer_name(lang, layer.name), 'value': layer.id} for layer in layers]

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
    reports_dropdown_relevance_type = get_sidebar_dropdown_relevance_type_values()

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
            zoomControl=False,
            center=(53.55, 9.99),
            style={
                'width': '100%', 
                'height': '100%',
                'z-index': '0'
            },
            id='map'
        ),
        html.Button(id='button_toggle_layers', children='-', style={'display': 'none'}),
        html.Div(  # here we create a 'fake' layers control that holds hidden components needed by callbacks
            id='layers_control',
            children=[
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
            style={'display': 'none'}
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
                # ---- sticky header + filter popup ----
                html.Div(
                    children=[
                        # title row
                        html.Div(
                            children=[
                                html.Span('Reports', style={
                                    'font-size': '14pt', 'font-weight': 'bold', 'color': '#404040',
                                }),
                                html.Div(
                                    children=[
                                        dcc.Checklist(
                                            id='autoscroll-toggle',
                                            options=[{'label': 'Auto-update', 'value': 'on'}],
                                            value=[],
                                            inputStyle={'margin-right': '3px'},
                                            style={'font-size': '9pt', 'color': '#888', 'white-space': 'nowrap'},
                                        ),
                                        html.Button(
                                            '↺ Reset Demo',
                                            id='demo-reset-button',
                                            n_clicks=0,
                                            style={
                                                'display': 'block' if os.environ.get('DEMO_MODE') == '1' else 'none',
                                                'font-size': '10px', 'padding': '2px 8px', 'cursor': 'pointer',
                                                'border-radius': '4px', 'border': '1px solid #ff8a65',
                                                'background': '#fff3e0', 'color': '#bf360c',
                                            }
                                        ),
                                    ],
                                    style={'display': 'flex', 'align-items': 'center', 'gap': '6px', 'margin-left': 'auto'},
                                ),
                            ],
                            style={'display': 'flex', 'align-items': 'center', 'gap': '6px'},
                        ),
                    ],
                    style={
                        'flex-shrink': '0',
                        'padding-bottom': '6px',
                        'border-bottom': '1px solid #e0e0e0',
                        'margin-bottom': '6px',
                    }
                ),
                # ---- new posts banner ----
                html.Button(
                    '↑ 0 new posts',
                    id='new-posts-banner',
                    n_clicks=0,
                    style={
                        'display': 'block', 'width': '100%', 'margin-bottom': '6px',
                        'font-size': '9px', 'padding': '4px 8px', 'cursor': 'pointer',
                        'border-radius': '4px', 'border': '1px solid #ddd',
                        'background': '#f5f5f5', 'color': '#aaa', 'font-weight': 'normal',
                        'text-align': 'center',
                    },
                ),
                # ---- scrollable report list ----
                html.Ul(
                    id='reports_list',
                    children=[],
                    style={
                        'margin': '0',
                        'padding': '0',
                        'list-style-type': 'none',
                        'overflow-y': 'auto',
                        'flex-shrink': '1',
                        'min-height': '0',
                    }
                )
            ],
            style={
                'display': 'flex',
                'flex-direction': 'column',
                'background-color': 'white',
                'border-right': '1px solid #ccc',
                'padding': '10px',
                'box-shadow': '2px 0 4px rgba(0,0,0,0.08)',
                'width': '370px',
                'flex-shrink': '0',
                'height': '100%',
                'overflow': 'visible',
            }
        ),
        dcc.Store(id='event_range_full', data=[]),                 # the full event range, selected by event_range_picker
        dcc.Store(id='event_range_selected', data=[]),             # the selected event range, selected by slider_events
        dcc.Store(id='geocoder_types', data={}),                   # the types of events the geocoder found
        dcc.Store(id='geocoder_entities', data=[]),                # the geocoder entities, selected by geocoder_entity_dropdown
        dcc.Interval(id='interval_refresh_reports', interval=10000 , n_intervals=0),  # refresh the reports every hour
        html.Div(id='dummy_output_1', style={'display': 'none'}),  # for some reason callback functions always need an output, so we create a dummy output for functions that dont return anything
        dcc.Store(id='active-report-locations'),   # list of {lat, lon} for active report's dots (offscreen arrows)
        dcc.Store(id='report-dots-data', data=[]), # all non-seen report dots: [{report_id, lat, lon, text, ...}]
        dcc.Store(id='active-report-id', data=None),  # id of selected report (its dots turn blue)
        dcc.Store(id='report-dots-tick', data=None),  # dummy store for clientside callback output
        dcc.Store(id='location-pick-mode', data=None),  # None = off, dict = {report_id, loc_index, mention}
        dcc.Store(id='locations-changed', data=0),      # incremented whenever a report's locations are edited (kept for render_report_polygons trigger)
        dcc.Location(id='url', refresh=False),                                # reads the current URL (for ?lang= param)
        dcc.Store(id='lang', data='de'),                                       # UI language: 'de' | 'en' — derived from ?lang= URL param
        dcc.Store(id='current-user', storage_type='local', data=None),       # username string, entered once on first load
        dcc.Store(id='user-state-snapshot', storage_type='memory', data={}), # {str(report_id): {hide, flag, flag_author, added}} – feeds clientside DOM-sync
        dcc.Store(id='filter-state', storage_type='local', data=None),       # persisted filter values (platform, event_type, etc.)
        dcc.Store(id='event-types-all', data=list(ALL_EVENT_TYPES)),          # static list passed to clientside chip callbacks
        html.Div(
            id='offscreen-indicators',
            style={
                'position': 'fixed', 'top': 0, 'left': 0, 'right': 0, 'bottom': 0,
                'zIndex': 499, 'pointerEvents': 'none',
            }
        ),
        html.Div(
            id='location-pick-overlay',
            children=[
                html.Div(
                    children=[
                        html.Span('📍 Click on the map to place a location', id='location-pick-overlay-text', style={'font-size': '13px'}),
                        html.Button(
                            'Cancel',
                            id='location-pick-cancel',
                            n_clicks=0,
                            style={
                                'font-size': '12px', 'padding': '3px 10px',
                                'border-radius': '4px', 'border': '1px solid rgba(255,255,255,0.5)',
                                'background': 'rgba(255,255,255,0.15)', 'color': '#fff', 'cursor': 'pointer',
                            },
                        ),
                    ],
                    style={'display': 'flex', 'align-items': 'center', 'gap': '10px'},
                ),
                html.Div(
                    children=[
                        html.Span('or', style={'font-size': '11px', 'opacity': '0.75'}),
                        dcc.Input(
                            id='location-search-input',
                            type='text',
                            placeholder='Search OpenStreetMap…',
                            n_submit=0,
                            value='',
                            debounce=False,
                            style={
                                'font-size': '11px', 'padding': '3px 8px', 'border-radius': '4px',
                                'border': 'none', 'outline': 'none', 'width': '210px', 'color': '#333',
                            },
                        ),
                        html.Button(
                            '🔍',
                            id='location-search-button',
                            n_clicks=0,
                            style={
                                'font-size': '12px', 'padding': '3px 8px', 'border-radius': '4px',
                                'border': '1px solid rgba(255,255,255,0.4)', 'background': 'rgba(255,255,255,0.15)',
                                'color': '#fff', 'cursor': 'pointer',
                            },
                        ),
                    ],
                    style={'display': 'flex', 'align-items': 'center', 'gap': '6px', 'margin-top': '7px'},
                ),
                html.Div(
                    id='location-search-results',
                    children=[],
                    style={
                        'display': 'none',
                        'margin-top': '4px',
                        'background': 'white', 'border': '1px solid #ddd', 'border-radius': '6px',
                        'box-shadow': '0 4px 16px rgba(0,0,0,0.15)', 'width': '100%',
                        'max-height': '240px', 'overflow-y': 'auto',
                    },
                ),
            ],
            style={
                'display': 'none',
                'position': 'fixed', 'top': '112px', 'left': '50%', 'transform': 'translateX(-50%)',
                'zIndex': 1100, 'background': 'rgba(21,101,192,0.92)', 'color': '#fff',
                'padding': '10px 18px', 'border-radius': '8px', 'pointer-events': 'auto',
                'flex-direction': 'column', 'align-items': 'flex-start', 'gap': '0',
            },
        ),
        dcc.Store(id='location-search-data', data=[]),
        dcc.Store(id='sidebar-loaded-at', storage_type='local', data=None),
        dcc.Store(id='fit-bounds-request', data=None),  # [[lat1,lon1],[lat2,lon2]] to fitBounds
        # ---- Username prompt modal ----
        html.Div(
            id='username-modal',
            children=[
                html.Div(
                    children=[
                        html.H3('Welcome', style={'margin': '0 0 8px 0', 'font-size': '16pt', 'color': '#333'}),
                        html.P('Enter your username to track your session state across browser refreshes.',
                               style={'font-size': '10pt', 'color': '#666', 'margin': '0 0 16px 0'}),
                        dcc.Input(
                            id='username-input',
                            type='text',
                            placeholder='Enter username…',
                            n_submit=0,
                            maxLength=64,
                            style={
                                'width': '100%', 'padding': '8px 10px', 'font-size': '12pt',
                                'border': '1px solid #ccc', 'border-radius': '6px',
                                'box-sizing': 'border-box', 'margin-bottom': '12px', 'outline': 'none',
                            },
                        ),
                        html.Button(
                            'Continue',
                            id='username-submit',
                            n_clicks=0,
                            style={
                                'width': '100%', 'padding': '8px', 'font-size': '11pt',
                                'border': 'none', 'border-radius': '6px', 'cursor': 'pointer',
                                'background': '#1565c0', 'color': '#fff', 'font-weight': 'bold',
                            },
                        ),
                        html.Div(id='username-error', style={'color': '#c62828', 'font-size': '9pt', 'margin-top': '8px'}),
                    ],
                    style={
                        'background': 'white', 'border-radius': '10px', 'padding': '28px 32px',
                        'box-shadow': '0 8px 32px rgba(0,0,0,0.22)', 'width': '360px', 'max-width': '90vw',
                    },
                ),
            ],
            style={
                'display': 'flex', 'position': 'fixed', 'top': 0, 'left': 0, 'right': 0, 'bottom': 0,
                'zIndex': 9999, 'background': 'rgba(0,0,0,0.45)', 'align-items': 'center', 'justify-content': 'center',
            },
        ),
    ]
    
    # layout_map[0..5] = dl.Map + map overlay controls (position:absolute)
    # layout_map[6]    = div_reports (the sidebar)
    # layout_map[7:]   = invisible elements (stores, interval, position:fixed overlays)
    map_panel_children = layout_map[:6]
    sidebar            = layout_map[6]
    invisible          = layout_map[7:]

    filter_bar = html.Div(
        id='filter-bar',
        children=[
            # Hidden checklist — holds state, driven by chip buttons
            dcc.Checklist(
                id='reports_dropdown_event_type',
                options=[{'label': e, 'value': e} for e in ALL_EVENT_TYPES],
                value=[e for e in ALL_EVENT_TYPES if e != 'Irrelevant'],
                style={'display': 'none'},
            ),
            # Left column — all other filters (78%)
            html.Div(
                children=[
                    # Location filter
                    html.Div(children=[
                        html.Span('Location', id='lbl-location', className='filter-label'),
                        dcc.RadioItems(
                            id='event_type_toggle',
                            options=[
                                {'label': 'All', 'value': 'all'},
                                {'label': '📍 Located', 'value': 'localized'},
                                {'label': '◎ Pending', 'value': 'pending'},
                                {'label': '∅ None', 'value': 'unlocalized'},
                            ],
                            value='all',
                            inline=True,
                            inputStyle={'margin-right': '2px'},
                            labelStyle={'margin-right': '6px'},
                            style={'font-size': '10pt', 'display': 'inline'},
                        ),
                    ], style={'display': 'flex', 'align-items': 'center', 'gap': '4px', 'white-space': 'nowrap'}),
                    html.Div(style={'width': '1px', 'height': '20px', 'background': '#e0e0e0', 'flex-shrink': '0'}),
                    # Relevance
                    html.Div(children=[
                        html.Span('Relevance', id='lbl-relevance', className='filter-label'),
                        dcc.Checklist(
                            id='reports_dropdown_relevance_type',
                            options=[{'label': r, 'value': r} for r in ALL_RELEVANCE_TYPES],
                            value=list(ALL_RELEVANCE_TYPES),
                            inline=True,
                            inputStyle={'margin-right': '3px'},
                            labelStyle={'margin-right': '6px', 'white-space': 'nowrap'},
                            style={'font-size': '10pt', 'display': 'inline'},
                        ),
                    ], style={'display': 'flex', 'align-items': 'center', 'gap': '4px', 'white-space': 'nowrap'}),
                    html.Div(style={'width': '1px', 'height': '20px', 'background': '#e0e0e0', 'flex-shrink': '0'}),
                    # Platform
                    html.Div(children=[
                        html.Span('Platform', id='lbl-platform', className='filter-label'),
                        dcc.Checklist(
                            id='reports_dropdown_platform',
                            options=[{'label': p, 'value': p} for p in reports_dropdown_platform],
                            value=list(reports_dropdown_platform),
                            inline=True,
                            inputStyle={'margin-right': '3px'},
                            labelStyle={'margin-right': '6px', 'white-space': 'nowrap'},
                            style={'font-size': '10pt', 'display': 'inline'},
                        ),
                    ], style={'display': 'flex', 'align-items': 'center', 'gap': '4px', 'white-space': 'nowrap'}),
                    html.Div(style={'width': '1px', 'height': '20px', 'background': '#e0e0e0', 'flex-shrink': '0'}),
                    # View / visibility
                    html.Div(children=[
                        html.Span('View', id='lbl-view', className='filter-label'),
                        dcc.Checklist(
                            id='reports_filter_visibility',
                            options=[
                                {'label': 'Show hidden', 'value': 'show_hidden'},
                                {'label': 'Flagged', 'value': 'show_flagged'},
                                {'label': 'Unflagged', 'value': 'show_unflagged'},
                            ],
                            value=['show_flagged', 'show_unflagged'],
                            inline=True,
                            inputStyle={'margin-right': '3px'},
                            labelStyle={'margin-right': '6px', 'white-space': 'nowrap'},
                            style={'font-size': '10pt', 'display': 'inline'},
                        ),
                    ], style={'display': 'flex', 'align-items': 'center', 'gap': '4px', 'white-space': 'nowrap'}),
                    html.Div(style={'width': '1px', 'height': '20px', 'background': '#e0e0e0', 'flex-shrink': '0'}),
                    # Event type chips
                    html.Div(children=[
                        html.Span('Type', id='lbl-type', className='filter-label'),
                        html.Div(
                            id='event-type-chips-container',
                            children=[
                                html.Button(
                                    e,
                                    id={'type': 'event-chip', 'index': e},
                                    n_clicks=0,
                                    className='filter-chip' + ('' if e == 'Irrelevant' else ' filter-chip-active'),
                                    title='Click to toggle · Shift+click to solo',
                                )
                                for e in ALL_EVENT_TYPES
                            ],
                            style={'display': 'inline-flex', 'flex-wrap': 'wrap', 'gap': '3px'},
                        ),
                    ], style={'display': 'flex', 'align-items': 'center', 'gap': '4px', 'white-space': 'nowrap'}),
                ],
                style={
                    'flex': '1', 'display': 'flex', 'align-items': 'center',
                    'gap': '12px', 'flex-wrap': 'wrap', 'padding': '4px 12px 4px 0',
                    'border-right': '1px solid #e0e0e0',
                }
            ),
            # Right column — Layers (22%)
            html.Div(
                children=[
                    html.Span('Layers', id='lbl-layers', className='filter-label'),
                    dcc.Checklist(
                        id='overlay_checklist',
                        options=layer_checkboxes,
                        value=[],
                        inline=True,
                        inputStyle={'margin-right': '3px'},
                        labelStyle={'margin-right': '6px', 'white-space': 'nowrap'},
                        style={'font-size': '10pt'},
                    ),
                ],
                style={
                    'flex': '0 0 25%', 'padding': '4px 0 4px 12px',
                }
            ),
        ],
        style={
            'display': 'flex',
            'align-items': 'stretch',
            'background': 'white',
            'border-bottom': '1px solid #e0e0e0',
            'padding': '5px 12px',
            'flex-shrink': '0',
            'box-shadow': '0 1px 3px rgba(0,0,0,0.07)',
            'z-index': '1001',
        }
    )

    return [
        html.Div(
            style={'display': 'flex', 'flex-direction': 'column', 'width': '100%', 'height': '100%'},
            children=[
                filter_bar,
                html.Div(
                    style={'display': 'flex', 'flex': '1', 'min-height': '0'},
                    children=[
                        sidebar,
                        html.Div(
                            map_panel_children,
                            style={'position': 'relative', 'flex': '1', 'height': '100%', 'overflow': 'hidden'},
                        ),
                    ]
                ),
            ]
        ),
        *invisible,
    ]

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
        max_lat = -math.inf
        min_lat = math.inf
        max_lon = -math.inf
        min_lon = math.inf
        if polygon_data and "coordinates" in polygon_data and len(polygon_data["coordinates"]) > 0:
            try:
                if polygon_data["type"] in {"Polygon", "MultiPolygon"}:
                    polygons = []
                    if polygon_data["type"] == "Polygon":
                        polygons = [polygon_data["coordinates"]]
                    elif polygon_data["type"] == "MultiPolygon":
                        polygons = polygon_data["coordinates"]

                    for idx_part, part in enumerate(polygons):
                        for idx_ring, ring in enumerate(part):
                            for coord in ring:
                                lon, lat = coord[0], coord[1]
                                if lat > max_lat:
                                    max_lat = lat
                                if lat < min_lat:
                                    min_lat = lat
                                if lon > max_lon:
                                    max_lon = lon
                                if lon < min_lon:
                                    min_lon = lon
                            polygon = dl.Polygon(
                                positions=[[coord[1], coord[0]] for coord in ring],
                                color="blue",
                                fill=True,
                                fillOpacity=0.15,
                                weight=2,
                                id=f'tmp_polygon_{identifier}_{idx_part}_{idx_ring}'
                            )
                            elements.append(polygon)
                elif polygon_data["type"] in {"LineString", "MultiLineString"}:
                    lines = []
                    if polygon_data["type"] == "LineString":
                        lines = [polygon_data["coordinates"]]
                        for coord in polygon_data["coordinates"]:
                            lon, lat = coord[0], coord[1]
                            if lat > max_lat:
                                max_lat = lat
                            if lat < min_lat:
                                min_lat = lat
                            if lon > max_lon:
                                max_lon = lon
                            if lon < min_lon:
                                min_lon = lon
                    elif polygon_data["type"] == "MultiLineString":
                        lines = polygon_data["coordinates"]
                        for line in polygon_data["coordinates"]:
                            for coord in line:
                                lon, lat = coord[0], coord[1]
                                if lat > max_lat:
                                    max_lat = lat
                                if lat < min_lat:
                                    min_lat = lat
                                if lon > max_lon:
                                    max_lon = lon
                                if lon < min_lon:
                                    min_lon = lon

                    for idx, line in enumerate(lines):
                        polyline = dl.Polyline(
                            positions=[[coord[1], coord[0]] for coord in line],
                            color="#00008B",  # DarkBlue hex color
                            weight=6,  # Thicker line, default is usually 3
                            dashArray=None,  # solid line (remove dashes if you want solid)
                            id=f'tmp_line_{identifier}_{idx}'
                        )
                        for coord in line:
                            lon, lat = coord[0], coord[1]
                            if lat > max_lat:
                                max_lat = lat
                            if lat < min_lat:
                                min_lat = lat
                            if lon > max_lon:
                                max_lon = lon
                            if lon < min_lon:
                                min_lon = lon
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
        return elements, (max_lat, min_lat, max_lon, min_lon)

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
                        c["props"]["id"].startswith("tmp_line") or
                        c["props"]["id"].startswith("tmp_layer")
                ))
            )
        ]
        return children

    @app.callback(
        Output('active-report-id', 'data'),
        Output('user-state-snapshot', 'data', allow_duplicate=True),
        [Input({'type': 'report-entry', 'index': ALL}, 'n_clicks')],
        State({'type': 'report-entry', 'index': ALL}, 'id'),
        State('active-report-id', 'data'),
        State('current-user', 'data'),
        State('user-state-snapshot', 'data'),
        prevent_initial_call=True
    )
    def select_report(report_nclicks, report_ids, current_active_id, username, snapshot):
        if not ctx.triggered:
            raise PreventUpdate
        if not report_nclicks or all((x is None or x == 0) for x in report_nclicks):
            raise PreventUpdate
        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        if not triggered_id_str or triggered_id_str == '.':
            raise PreventUpdate
        report_id = json.loads(triggered_id_str).get('index')
        if report_id is None:
            raise PreventUpdate
        new_active_id = None if report_id == current_active_id else report_id
        # Set new=False to mark this report as acknowledged; update snapshot for instant badge removal
        updated_snapshot = dict(snapshot or {})
        entry = dict(updated_snapshot.get(str(report_id), {}))
        entry['new'] = False
        updated_snapshot[str(report_id)] = entry
        if username:
            try:
                engine, session = autoconnect_db()
                try:
                    _upsert_user_state(username, report_id, session, new=False)
                    session.commit()
                finally:
                    session.close()
                    engine.dispose()
            except Exception:
                pass
        return new_active_id, updated_snapshot

    @app.callback(
        Output('user-state-snapshot', 'data', allow_duplicate=True),
        Input('active-report-id', 'data'),
        State('current-user', 'data'),
        State('user-state-snapshot', 'data'),
        prevent_initial_call=True,
    )
    def acknowledge_active_report(report_id, username, snapshot):
        """Persist new=False whenever a report becomes active (covers map-dot clicks
        which bypass the sidebar select_report callback)."""
        if not report_id or not username:
            raise PreventUpdate
        updated_snapshot = dict(snapshot or {})
        entry = dict(updated_snapshot.get(str(report_id), {}))
        if not entry.get('new', True):
            raise PreventUpdate  # already acknowledged, nothing to do
        entry['new'] = False
        updated_snapshot[str(report_id)] = entry
        try:
            engine, session = autoconnect_db()
            try:
                _upsert_user_state(username, report_id, session, new=False)
                session.commit()
            finally:
                session.close()
                engine.dispose()
        except Exception:
            pass
        return updated_snapshot

    @app.callback(
        Output('map', 'children', allow_duplicate=False),
        Output('active-report-locations', 'data'),
        Input('active-report-id', 'data'),
        Input('locations-changed', 'data'),
        State('map', 'children'),
        State('current-user', 'data'),
        prevent_initial_call=True
    )
    def render_report_polygons(report_id, _locations_changed, map_children, username):
        children = get_children(map_children)
        if not report_id:
            return children, []

        engine, session = autoconnect_db()
        try:
            report = session.query(Report).filter(Report.id == report_id).first()
            if not report:
                return children, []
            # User override locations from DB
            effective_locations = report.locations or []
            if username:
                urs = session.query(UserReportState).filter_by(
                    username=username, report_id=report_id
                ).first()
                if urs and urs.locations is not None:
                    effective_locations = urs.locations
        finally:
            session.close()
            engine.dispose()

        if not effective_locations:
            return children, []

        polygons = []
        dot_locations = []
        for loc in effective_locations:
            if 'osm_id' not in loc:
                continue
            lat, lon = loc.get('lat'), loc.get('lon')
            if lat is None or lon is None:
                continue
            dot_locations.append({'lat': lat, 'lon': lon})
            title = loc.get('name') or loc.get('mention') or str(loc.get('osm_id', ''))
            new_elements, _ = create_elements(loc, identifier=title)
            polygons.extend(new_elements)

        if polygons:
            tmp_layer = dl.LayerGroup(children=polygons, id=f'tmp_layer_{time.time()}')
            children = [tmp_layer] + children

        return children, dot_locations or []


    @app.callback(
        Output('geocoder_result_types', 'children'),
        Output('geocoder_result_description', 'children'),
        Output('geocoder_result_url', 'children'),
        Output('geocoder_result_url', 'href'),
        Output('geocoder_result_lat', 'children'),
        Output('geocoder_result_lon', 'children'),
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

            new_rectangles, (max_lat, min_lat, max_lon, min_lon) = create_elements(e, identifier=title)
            rectangles += new_rectangles

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

        # selected entity for sidebar
        sel_e = entities[sel]
        sel_lat = float(sel_e['lat'])
        sel_lon = float(sel_e['lon'])
        sel_desc = sel_e.get('name', '')
        sel_url = f"https://www.openstreetmap.org/{sel_e['osm_type']}/{sel_e['osm_id']}"

        new_children = base + markers + rectangles

        return type_children, sel_desc, sel_url, sel_url, f'Latitude: {sel_lat}', f'Longitude: {sel_lon}', new_children


    # ---- Username modal ----
    @app.callback(
        Output('username-modal', 'style'),
        Output('current-user', 'data'),
        Output('username-error', 'children'),
        Input('username-submit', 'n_clicks'),
        Input('username-input', 'n_submit'),
        Input('current-user', 'data'),
        State('username-input', 'value'),
        State('lang', 'data'),
        prevent_initial_call=False,
    )
    def handle_username_prompt(n_clicks, n_submit, current_user, input_value, lang):
        _modal_hidden = {'display': 'none'}
        _modal_shown  = {
            'display': 'flex', 'position': 'fixed', 'top': 0, 'left': 0, 'right': 0, 'bottom': 0,
            'zIndex': 9999, 'background': 'rgba(0,0,0,0.45)', 'align-items': 'center', 'justify-content': 'center',
        }
        triggered = ctx.triggered[0]['prop_id'] if ctx.triggered else ''

        # On page load: if already set, hide modal
        if 'current-user' in triggered or not triggered:
            if current_user:
                return _modal_hidden, current_user, ''
            else:
                return _modal_shown, dash.no_update, ''

        # Submit action
        if 'username-submit' in triggered or 'username-input' in triggered:
            _lang = lang or 'de'
            val = (input_value or '').strip()
            if not val:
                return _modal_shown, dash.no_update, _t(_lang, 'err_empty')
            if len(val) > 64:
                return _modal_shown, dash.no_update, _t(_lang, 'err_too_long')
            return _modal_hidden, val, ''

        return _modal_shown, dash.no_update, ''

    # ── URL → lang store ─────────────────────────────────────────────────────
    @app.callback(
        Output('lang', 'data'),
        Input('url', 'search'),
    )
    def set_lang_from_url(search):
        """Derive language from ?lang= override, then Accept-Language header, then default to 'de'."""
        import urllib.parse
        import flask
        # 1. Explicit URL override takes precedence
        if search:
            params = urllib.parse.parse_qs(search.lstrip('?'))
            if 'lang' in params:
                lang = params['lang'][0]
                return lang if lang in ('de', 'en') else 'de'
        # 2. Browser's Accept-Language header
        accept = flask.request.headers.get('Accept-Language', '')
        for tag in accept.replace(' ', '').split(','):
            primary = tag.split(';')[0].split('-')[0].lower()
            if primary in ('de', 'en'):
                return primary
        return 'de'

    # ── Push lang strings to JS (window._langStrings) ────────────────────────
    _js_strings = TRANSLATIONS  # push all keys so JS _t() can translate view labels too
    app.clientside_callback(
        """
        function(lang) {
            var strings = %s;
            window._langStrings = strings[lang] || strings['de'];
            return window.dash_clientside.no_update;
        }
        """ % json.dumps(_js_strings),
        Output('lang', 'data', allow_duplicate=True),
        Input('lang', 'data'),
        prevent_initial_call=True,
    )

    # ── Apply lang to filter bar labels and checklist options ────────────────
    @app.callback(
        Output('lbl-location', 'children'),
        Output('lbl-relevance', 'children'),
        Output('lbl-platform', 'children'),
        Output('lbl-view', 'children'),
        Output('lbl-type', 'children'),
        Output('lbl-layers', 'children'),
        Output('event_type_toggle', 'options'),
        Output('overlay_checklist', 'options', allow_duplicate=True),
        Input('lang', 'data'),
        prevent_initial_call='initial_duplicate',
    )
    def apply_lang(lang):
        lg = lang or 'de'
        loc_options = [
            {'label': _t(lg, 'loc_all'),     'value': 'all'},
            {'label': _t(lg, 'loc_located'), 'value': 'localized'},
            {'label': _t(lg, 'loc_pending'), 'value': 'pending'},
            {'label': _t(lg, 'loc_none'),    'value': 'unlocalized'},
        ]
        layer_options = build_layer_checkboxes(lang=lg)
        return (
            _t(lg, 'location'), _t(lg, 'relevance'), _t(lg, 'platform'),
            _t(lg, 'view'), _t(lg, 'type'), _t(lg, 'layers'),
            loc_options, layer_options,
        )

    # Build the sidebar list — fires on filter changes and initial load, NOT on interval
    def _vis_flags(filter_visibility):
        vis = filter_visibility or []
        return {
            'hide_seen':      'show_hidden'   not in vis,
            'hide_flagged':   'show_flagged'  not in vis,
            'hide_unflagged': 'show_unflagged' not in vis,
        }

    def _build_sidebar_content(filter_platform, filter_event_type, filter_relevance_type,
                                event_type_toggle, username=None, session=None,
                                filter_visibility=None, max_timestamp=None,
                                lang='de',
                                # legacy params for callers that still pass report_state/locs_dict:
                                report_state=None, locs_dict=None):
        eff_platform, eff_events, eff_relevance = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
        if username and session:
            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, _snap = _get_user_state(username, session)
        else:
            # fallback to legacy stores when username not available yet
            seen_ids, flagged_authors, user_locs_map = _parse_stores(report_state, locs_dict)
            added_ids = {int(k) for k, v in (report_state or {}).items() if v.get('added')}
            new_ids = set()
        return get_sidebar_content(
            filter_platform=eff_platform,
            filter_event_type=eff_events,
            filter_relevance_type=eff_relevance,
            loc_filter=event_type_toggle or 'all',
            seen_ids=seen_ids,
            flagged_authors=flagged_authors,
            user_locs_map=user_locs_map,
            max_timestamp=max_timestamp,
            added_ids=added_ids,
            new_ids=new_ids,
            lang=lang,
            **_vis_flags(filter_visibility),
        )

    @app.callback(
        Output('reports_list', 'children'),
        Output('active-report-id', 'data', allow_duplicate=True),
        Output('sidebar-loaded-at', 'data'),
        Output('new-posts-banner', 'children', allow_duplicate=True),
        Output('new-posts-banner', 'style', allow_duplicate=True),
        Output('user-state-snapshot', 'data', allow_duplicate=True),
        Output('report-dots-data', 'data', allow_duplicate=True),
        Input('reports_dropdown_platform', 'value'),
        Input('reports_dropdown_event_type', 'value'),
        Input('reports_dropdown_relevance_type', 'value'),
        Input('event_type_toggle', 'value'),
        Input('new-posts-banner', 'n_clicks'),
        Input('reports_filter_visibility', 'value'),
        Input('current-user', 'data'),
        State('sidebar-loaded-at', 'data'),
        State('active-report-id', 'data'),
        State('autoscroll-toggle', 'value'),
        State('lang', 'data'),
        prevent_initial_call='initial_duplicate',
    )
    def update_reports(filter_platform, filter_event_type, filter_relevance_type, event_type_toggle,
                       _banner_clicks, filter_visibility, username, old_loaded_at, active_report_id, autoupdate, lang):
        if not username:
            raise PreventUpdate
        eff_platform, eff_events, eff_relevance = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
        triggered = ctx.triggered[0]['prop_id'] if ctx.triggered else ''
        is_banner_click = 'new-posts-banner' in triggered
        is_initial_load = not old_loaded_at

        engine, session = autoconnect_db()
        try:
            def _query_reports_inner(since=None):
                q = session.query(Report).filter(Report.timestamp <= datetime.now(timezone.utc))
                if since:
                    q = q.filter(Report.timestamp > since)
                if os.environ.get('DEMO_MODE') == '1':
                    q = q.filter(Report.identifier.like('demo-%'))
                if eff_platform:
                    from sqlalchemy import or_ as _or
                    q = q.filter(_or(*[Report.platform.like(f'{p}%') for p in eff_platform]))
                if eff_events:
                    q = q.filter(Report.event_type.in_(eff_events))
                if eff_relevance:
                    q = q.filter(Report.relevance.in_(eff_relevance))
                return q.all()

            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot = _get_user_state(username, session)

            if is_initial_load:
                # Admit all currently matching reports as the baseline view.
                all_reports = _query_reports_inner()
                _bulk_admit_reports(username, [r.id for r in all_reports], session)
                if active_report_id:
                    _upsert_user_state(username, active_report_id, session, new=False)
                session.commit()
                seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot = _get_user_state(username, session)
            elif is_banner_click:
                new_reports = _query_reports_inner(since=None)
                new_reports = _filter_by_display(
                    new_reports,
                    event_type_toggle or 'all',
                    seen_ids, flagged_authors, user_locs_map,
                    _vis_flags(filter_visibility),
                )
                if active_report_id:
                    _upsert_user_state(username, active_report_id, session, new=False)
                if new_reports:
                    _bulk_admit_reports(username, [r.id for r in new_reports], session)
                session.commit()
                seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot = _get_user_state(username, session)

            lang = lang or 'de'
            sidebar_content = _build_sidebar_content(
                filter_platform, filter_event_type, filter_relevance_type,
                event_type_toggle, username=username, session=session,
                filter_visibility=filter_visibility, lang=lang,
            )
            dots = dash.no_update
            if is_initial_load or is_banner_click:
                dots = _build_dots(
                    session, seen_ids=seen_ids, flagged_authors=flagged_authors,
                    user_locs_map=user_locs_map,
                    filter_platform=eff_platform, filter_event_type=eff_events,
                    filter_relevance_type=eff_relevance,
                    loc_filter=event_type_toggle or 'all',
                    new_ids=new_ids, added_ids=added_ids,
                    **_vis_flags(filter_visibility),
                )
        finally:
            session.close()
            engine.dispose()

        _banner_base = {
            'display': 'block', 'width': '100%', 'margin-bottom': '6px',
            'font-size': '9px', 'padding': '4px 8px', 'cursor': 'pointer',
            'border-radius': '4px', 'text-align': 'center',
        }
        _banner_idle   = {**_banner_base, 'border': '1px solid #ddd', 'background': '#f5f5f5', 'color': '#aaa', 'font-weight': 'normal'}
        _banner_active = {**_banner_base, 'border': '1px solid #42a5f5', 'background': '#e3f2fd', 'color': '#1565c0', 'font-weight': 'bold'}

        reset_active = None if not is_banner_click else dash.no_update
        if is_initial_load or is_banner_click:
            return sidebar_content, reset_active, datetime.now(timezone.utc).isoformat(), new_posts_label(lang, 0), _banner_idle, snapshot, dots
        else:
            # Filter change: find pending posts that match the new filters.
            pending = []
            if old_loaded_at:
                try:
                    engine2, session2 = autoconnect_db()
                    try:
                        q = session2.query(Report).filter(Report.timestamp <= datetime.now(timezone.utc))
                        if os.environ.get('DEMO_MODE') == '1':
                            q = q.filter(Report.identifier.like('demo-%'))
                        if eff_platform:
                            from sqlalchemy import or_ as _or
                            q = q.filter(_or(*[Report.platform.like(f'{p}%') for p in eff_platform]))
                        if eff_events:
                            q = q.filter(Report.event_type.in_(eff_events))
                        if eff_relevance:
                            q = q.filter(Report.relevance.in_(eff_relevance))
                        pending = q.all()
                        pending = _filter_by_display(
                            pending,
                            event_type_toggle or 'all',
                            seen_ids, flagged_authors, user_locs_map,
                            _vis_flags(filter_visibility),
                        )
                        pending = [r for r in pending if r.id not in added_ids]
                    finally:
                        session2.close()
                        engine2.dispose()
                except Exception:
                    pending = []

            if autoupdate and 'on' in autoupdate and pending:
                # Auto-update on: admit pending posts immediately, same as interval path.
                engine3, session3 = autoconnect_db()
                try:
                    _bulk_admit_reports(username, [r.id for r in pending], session3)
                    session3.commit()
                    _, _, _, _, _, snapshot = _get_user_state(username, session3)
                    sidebar_content = _build_sidebar_content(
                        filter_platform, filter_event_type, filter_relevance_type,
                        event_type_toggle, username=username, session=session3,
                        filter_visibility=filter_visibility, lang=lang,
                    )
                finally:
                    session3.close()
                    engine3.dispose()
                return sidebar_content, reset_active, datetime.now(timezone.utc).isoformat(), new_posts_label(lang, 0), _banner_idle, snapshot, dash.no_update

            count = len(pending)
            if count > 0:
                return sidebar_content, reset_active, dash.no_update, new_posts_label(lang, count), _banner_active, snapshot, dash.no_update
            else:
                return sidebar_content, reset_active, dash.no_update, new_posts_label(lang, 0), _banner_idle, snapshot, dash.no_update

    # Check for new posts on each interval tick.
    # Auto-update mode: rebuild the list immediately when new posts arrive.
    # Manual mode: show the banner so the user can click to refresh.
    @app.callback(
        Output('new-posts-banner', 'children', allow_duplicate=True),
        Output('new-posts-banner', 'style', allow_duplicate=True),
        Output('reports_list', 'children', allow_duplicate=True),
        Output('sidebar-loaded-at', 'data', allow_duplicate=True),
        Output('user-state-snapshot', 'data', allow_duplicate=True),
        Input('interval_refresh_reports', 'n_intervals'),
        Input('autoscroll-toggle', 'value'),
        State('sidebar-loaded-at', 'data'),
        State('reports_dropdown_platform', 'value'),
        State('reports_dropdown_event_type', 'value'),
        State('reports_dropdown_relevance_type', 'value'),
        State('event_type_toggle', 'value'),
        State('reports_filter_visibility', 'value'),
        State('current-user', 'data'),
        State('active-report-id', 'data'),
        State('lang', 'data'),
        prevent_initial_call=True,
    )
    def check_new_posts(_n, autoupdate, loaded_at, filter_platform, filter_event_type,
                        filter_relevance_type, loc_filter, filter_visibility, username, active_report_id, lang):
        if not username or not loaded_at:
            raise PreventUpdate
        try:
            since = datetime.fromisoformat(loaded_at)
        except Exception:
            raise PreventUpdate
        eff_platform, eff_events, eff_relevance = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
        engine, session = autoconnect_db()
        _banner_base = {
            'display': 'block', 'width': '100%', 'margin-bottom': '6px',
            'font-size': '9px', 'padding': '4px 8px', 'cursor': 'pointer',
            'border-radius': '4px', 'text-align': 'center',
        }
        _banner_idle = {**_banner_base, 'border': '1px solid #ddd', 'background': '#f5f5f5', 'color': '#aaa', 'font-weight': 'normal'}
        try:
            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot = _get_user_state(username, session)

            q = session.query(Report).filter(
                Report.timestamp > since,
                Report.timestamp <= datetime.now(timezone.utc),
            )
            if os.environ.get('DEMO_MODE') == '1':
                q = q.filter(Report.identifier.like('demo-%'))
            if eff_platform:
                from sqlalchemy import or_ as _or
                q = q.filter(_or(*[Report.platform.like(f'{p}%') for p in eff_platform]))
            if eff_events:
                q = q.filter(Report.event_type.in_(eff_events))
            if eff_relevance:
                q = q.filter(Report.relevance.in_(eff_relevance))
            # Fix: filter by integer report IDs (not identifiers)
            q = q.filter(Report.id.notin_(added_ids))
            new_reports = q.all()

            new_reports = _filter_by_display(
                new_reports,
                loc_filter or 'all',
                seen_ids, flagged_authors, user_locs_map,
                _vis_flags(filter_visibility),
            )
            count = len(new_reports)

            lang = lang or 'de'
            if count == 0:
                return new_posts_label(lang, 0), _banner_idle, dash.no_update, dash.no_update, dash.no_update

            if autoupdate and 'on' in autoupdate:
                _bulk_admit_reports(username, [r.id for r in new_reports], session)
                if active_report_id:
                    _upsert_user_state(username, active_report_id, session, new=False)
                session.commit()
                _, _, _, _, _, snapshot = _get_user_state(username, session)
                new_loaded_at = datetime.now(timezone.utc).isoformat()
                sidebar = _build_sidebar_content(
                    filter_platform, filter_event_type, filter_relevance_type,
                    loc_filter, username=username, session=session,
                    filter_visibility=filter_visibility, lang=lang,
                )
                return new_posts_label(lang, 0), _banner_idle, sidebar, new_loaded_at, snapshot

            # Manual mode: show banner only, no state change
            return new_posts_label(lang, count), {**_banner_base, 'border': '1px solid #42a5f5', 'background': '#e3f2fd', 'color': '#1565c0', 'font-weight': 'bold'}, dash.no_update, dash.no_update, dash.no_update
        finally:
            session.close()
            engine.dispose()
    
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

    # Off-screen pin indicator: renders orange arrow divs at viewport edges pointing toward
    # any active-report pin outside the current map view. Clicking flies the Leaflet map
    # directly via window._leafletMap (captured by assets/leaflet_capture.js).
    # Pass locations to JS and trigger repositionArrows. Arrow DOM is managed entirely by
    # assets/leaflet_capture.js so we return no_update to prevent React from wiping JS nodes.
    app.clientside_callback(
        """
        function(locations, _interval) {
            window._offscreenLocations = locations;
            if (window.repositionArrows) window.repositionArrows();
            return window.dash_clientside.no_update;
        }
        """,
        Output('offscreen-indicators', 'children'),
        Input('active-report-locations', 'data'),
        Input('interval_refresh_reports', 'n_intervals'),
    )

    # Fetch all non-seen report dots on every interval tick
    @app.callback(
        Output('report-dots-data', 'data', allow_duplicate=True),
        Input('interval_refresh_reports', 'n_intervals'),
        Input('reports_dropdown_platform', 'value'),
        Input('reports_dropdown_event_type', 'value'),
        Input('reports_dropdown_relevance_type', 'value'),
        Input('event_type_toggle', 'value'),
        Input('reports_filter_visibility', 'value'),
        State('current-user', 'data'),
        prevent_initial_call='initial_duplicate'
    )
    def fetch_report_dots(_n, filter_platform, filter_event_type, filter_relevance_type, loc_filter,
                          filter_visibility, username):
        eff_platform, eff_events, eff_relevance = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
        engine, session = autoconnect_db()
        try:
            if username:
                seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, _ = _get_user_state(username, session)
            else:
                seen_ids, flagged_authors, user_locs_map, added_ids, new_ids = set(), set(), {}, set(), set()
            return _build_dots(session, seen_ids=seen_ids, flagged_authors=flagged_authors,
                                user_locs_map=user_locs_map,
                                filter_platform=eff_platform,
                                filter_event_type=eff_events,
                                filter_relevance_type=eff_relevance,
                                new_ids=new_ids, added_ids=added_ids,
                                loc_filter=loc_filter or 'all',
                                **_vis_flags(filter_visibility))
        finally:
            session.close()
            engine.dispose()

    # Fit the map to all georeferenced locations of the clicked report
    @app.callback(
        Output('fit-bounds-request', 'data'),
        Input({'type': 'center-button', 'index': ALL}, 'n_clicks'),
        State('current-user', 'data'),
        prevent_initial_call=True,
    )
    def center_map_on_report(n_clicks_list, username):
        if not any(n for n in (n_clicks_list or []) if n):
            raise PreventUpdate
        triggered = ctx.triggered_id
        if not triggered:
            raise PreventUpdate
        report_id = triggered['index']
        engine, session = autoconnect_db()
        try:
            # look up locations: user override first, then DB
            locs = None
            if username:
                urs = session.query(UserReportState).filter_by(
                    username=username, report_id=report_id
                ).first()
                if urs and urs.locations is not None:
                    locs = urs.locations
            if locs is None:
                report = session.query(Report).filter(Report.id == report_id).first()
                locs = report.locations if report else []
        finally:
            session.close()
            engine.dispose()
        georef = [loc for loc in (locs or []) if 'osm_id' in loc and loc.get('lat') and loc.get('lon')]
        if not georef:
            raise PreventUpdate
        lats = [loc['lat'] for loc in georef]
        lons = [loc['lon'] for loc in georef]
        pad = 0.01  # ~1 km padding so a single point doesn't zoom to maximum
        return [[min(lats) - pad, min(lons) - pad], [max(lats) + pad, max(lons) + pad]]

    # Clientside: call window._leafletMap.fitBounds() whenever a bounds request arrives
    app.clientside_callback(
        """
        function(bounds) {
            if (!bounds || !window._leafletMap) return window.dash_clientside.no_update;
            setTimeout(function() {
                try { window._leafletMap.fitBounds(bounds, {padding: [20, 20]}); } catch(e) {}
            }, 50);
            return window.dash_clientside.no_update;
        }
        """,
        Output('report-dots-tick', 'data', allow_duplicate=True),
        Input('fit-bounds-request', 'data'),
        prevent_initial_call=True,
    )

    # Toggle hide state for a report; immediately rebuild sidebar + dots
    @app.callback(
        Output('user-state-snapshot', 'data', allow_duplicate=True),
        Output('report-dots-data', 'data', allow_duplicate=True),
        Output('reports_list', 'children', allow_duplicate=True),
        Input({'type': 'seen-button', 'index': ALL}, 'n_clicks'),
        State('current-user', 'data'),
        State('reports_dropdown_platform', 'value'),
        State('reports_dropdown_event_type', 'value'),
        State('reports_dropdown_relevance_type', 'value'),
        State('event_type_toggle', 'value'),
        State('reports_filter_visibility', 'value'),
        State('sidebar-loaded-at', 'data'),
        State('lang', 'data'),
        prevent_initial_call=True
    )
    def toggle_report_seen(n_clicks_list, username,
                           filter_platform, filter_event_type, filter_relevance_type, event_type_toggle,
                           filter_visibility, loaded_at, lang):
        if not username:
            raise PreventUpdate
        if not ctx.triggered:
            raise PreventUpdate
        if all(n is None or n == 0 for n in n_clicks_list):
            raise PreventUpdate

        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        report_id = json.loads(triggered_id_str).get('index')
        if report_id is None:
            raise PreventUpdate

        eff_platform, eff_events, eff_relevance = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)

        engine, session = autoconnect_db()
        try:
            # Get current hide state
            existing = session.query(UserReportState).filter_by(
                username=username, report_id=report_id
            ).first()
            new_hide = not (existing.hide if existing else False)
            _upsert_user_state(username, report_id, session, hide=new_hide)
            session.commit()

            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot = _get_user_state(username, session)
            vis = _vis_flags(filter_visibility)
            dots = _build_dots(session, seen_ids=seen_ids, flagged_authors=flagged_authors,
                                user_locs_map=user_locs_map,
                                filter_platform=eff_platform, filter_event_type=eff_events,
                                filter_relevance_type=eff_relevance, loc_filter=event_type_toggle or 'all',
                                new_ids=new_ids, added_ids=added_ids, **vis)
            sidebar = _build_sidebar_content(
                filter_platform, filter_event_type, filter_relevance_type,
                event_type_toggle, username=username, session=session,
                filter_visibility=filter_visibility,
                max_timestamp=loaded_at, lang=lang or 'de',
            )
            return snapshot, dots, sidebar
        finally:
            session.close()
            engine.dispose()

    # Server-side flag toggle — replaces the JS _toggleAuthorFlag for sidebar flag buttons
    @app.callback(
        Output('user-state-snapshot', 'data', allow_duplicate=True),
        Output('report-dots-data', 'data', allow_duplicate=True),
        Output('reports_list', 'children', allow_duplicate=True),
        Input({'type': 'flag-button', 'index': ALL, 'author': ALL}, 'n_clicks'),
        State('current-user', 'data'),
        State('reports_dropdown_platform', 'value'),
        State('reports_dropdown_event_type', 'value'),
        State('reports_dropdown_relevance_type', 'value'),
        State('event_type_toggle', 'value'),
        State('reports_filter_visibility', 'value'),
        State('sidebar-loaded-at', 'data'),
        State('lang', 'data'),
        prevent_initial_call=True,
    )
    def toggle_author_flag(n_clicks_list, username,
                           filter_platform, filter_event_type, filter_relevance_type,
                           event_type_toggle, filter_visibility, loaded_at, lang):
        if not username:
            raise PreventUpdate
        if not ctx.triggered or all(n is None or n == 0 for n in n_clicks_list):
            raise PreventUpdate
        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        try:
            id_dict = json.loads(triggered_id_str)
            author = id_dict.get('author', '')
        except Exception:
            raise PreventUpdate
        if not author:
            raise PreventUpdate

        eff_platform, eff_events, eff_relevance = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)

        engine, session = autoconnect_db()
        try:
            # Determine current flag state for this author
            existing_flagged = session.query(UserReportState).filter_by(
                username=username, flag=True, flag_author=author
            ).first()
            new_flag = not bool(existing_flagged)

            # Get all reports by this author that have a state row for this user
            rows_for_author = session.query(UserReportState).filter(
                UserReportState.username == username,
                UserReportState.flag_author == author,
            ).all()
            for row in rows_for_author:
                row.flag = new_flag
            session.flush()

            # Also ensure rows exist for all reports by this author (via reports table)
            author_reports = session.query(Report).filter(Report.author == author).all()
            for r in author_reports:
                existing = session.query(UserReportState).filter_by(
                    username=username, report_id=r.id
                ).first()
                if existing:
                    existing.flag = new_flag
                    existing.flag_author = author if new_flag else existing.flag_author
                else:
                    _upsert_user_state(username, r.id, session, flag=new_flag, flag_author=author if new_flag else None)
            session.commit()

            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot = _get_user_state(username, session)
            vis = _vis_flags(filter_visibility)
            dots = _build_dots(session, seen_ids=seen_ids, flagged_authors=flagged_authors,
                                user_locs_map=user_locs_map,
                                filter_platform=eff_platform, filter_event_type=eff_events,
                                filter_relevance_type=eff_relevance, loc_filter=event_type_toggle or 'all',
                                new_ids=new_ids, added_ids=added_ids, **vis)
            sidebar = _build_sidebar_content(
                filter_platform, filter_event_type, filter_relevance_type,
                event_type_toggle, username=username, session=session,
                filter_visibility=filter_visibility,
                max_timestamp=loaded_at, lang=lang or 'de',
            )
            return snapshot, dots, sidebar
        finally:
            session.close()
            engine.dispose()

    # Clientside: push dot data + report-state to JS globals; update sidebar DOM in one pass
    app.clientside_callback(
        """
        function(dots, activeId, _loadedAt, reportState) {
            var state = reportState || {};
            window._reportDotsData = dots || [];
            window._activeReportId = activeId;
            window._reportState    = state;

            // Derive seenIds and flaggedAuthors from unified state
            window._seenIds = Object.keys(state).filter(function(id) {
                return state[id].hide;
            }).map(Number);
            window._flaggedAuthors = Object.values(state)
                .filter(function(s) { return s.flag && s.author; })
                .map(function(s) { return s.author; })
                .filter(function(v, i, a) { return a.indexOf(v) === i; });

            if (window.updateReportDots) window.updateReportDots();

            // Update seen-button labels/styles + entry opacity
            document.querySelectorAll('[id*="seen-button"]').forEach(function(btn) {
                try {
                    var idObj  = JSON.parse(btn.id);
                    var isSeen = !!((state[String(idObj.index)] || {}).hide);
                    var li     = btn.closest('li');
                    if (li) li.style.opacity = isSeen ? '0.5' : '1';
                    btn.textContent       = isSeen ? _t('unhide', 'Unhide') : _t('hide', 'Hide');
                    btn.style.border      = isSeen ? '1px solid #a5d6a7' : '1px solid #ddd';
                    btn.style.background  = isSeen ? '#e8f5e9' : '#fafafa';
                    btn.style.color       = isSeen ? '#2e7d32' : '#888';
                    btn.style.fontWeight  = isSeen ? 'bold' : 'normal';
                } catch(e) {}
            });

            // Update flag-button labels/styles + li outline
            var flagged = window._flaggedAuthors;
            document.querySelectorAll('[id*="flag-button"]').forEach(function(btn) {
                try {
                    var idObj     = JSON.parse(btn.id);
                    var author    = idObj.author || '';
                    var isFlagged = !!author && flagged.indexOf(author) !== -1;
                    btn.textContent      = isFlagged ? _t('unflag', 'Unflag') : _t('flag', 'Flag');
                    btn.style.border     = isFlagged ? '1px solid #e65100' : '1px solid #ddd';
                    btn.style.background = isFlagged ? '#fff3e0' : '#fafafa';
                    btn.style.color      = isFlagged ? '#e65100' : '#888';
                    btn.style.fontWeight = isFlagged ? 'bold' : 'normal';
                    var li = btn.closest('li');
                    if (li) li.style.outline = isFlagged ? '2px solid #e65100' : 'none';
                } catch(e) {}
            });

            // Update NEW badges based on snapshot
            Object.keys(state).forEach(function(rid) {
                var badge = document.getElementById('new-badge-' + rid);
                if (badge) {
                    badge.style.display = state[rid].new ? 'inline-block' : 'none';
                }
            });

            // Highlight active report entry — only scroll when the active ID actually changed
            var _activeId = activeId;
            var _activeChanged = _activeId !== window._lastHighlightedActiveId;
            window._lastHighlightedActiveId = _activeId;
            setTimeout(function() {
                document.querySelectorAll('.report-entry-active').forEach(function(el) {
                    el.classList.remove('report-entry-active');
                });
                if (_activeId !== null && _activeId !== undefined) {
                    var el = document.getElementById('{"index":' + _activeId + ',"type":"report-entry"}');
                    if (el) {
                        var li = el.closest('li');
                        if (li) {
                            li.classList.add('report-entry-active');
                            if (_activeChanged) {
                                li.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            }
                        }
                    }
                }
            }, 150);
            return window.dash_clientside.no_update;
        }
        """,
        Output('report-dots-tick', 'data'),
        Input('report-dots-data', 'data'),
        Input('active-report-id', 'data'),
        Input('sidebar-loaded-at', 'data'),
        Input('user-state-snapshot', 'data'),
    )



    # ---- Shared helpers for location callbacks ----
    def _normalize_filters(filter_platform, filter_event_type, filter_relevance_type):
        """Convert checklist values to filter args (None / [] = no filter)."""
        all_platforms = get_sidebar_dropdown_platform_values()
        plats = list(filter_platform or [])
        ets   = list(filter_event_type or [])
        rels  = list(filter_relevance_type or [])
        eff_platform  = None if set(plats) >= set(all_platforms) else (plats or None)
        eff_events    = [] if set(ets) >= set(ALL_EVENT_TYPES) else ets
        eff_relevance = [] if set(rels) >= set(ALL_RELEVANCE_TYPES) else rels
        return eff_platform, eff_events, eff_relevance

    def _parse_stores(report_state, locs_dict):
        """Legacy helper kept for compatibility during transition; prefer _get_user_state."""
        state = report_state or {}
        seen_ids = {int(k) for k, v in state.items() if v.get('hide')}
        flagged_authors = {v.get('author', '') for v in state.values()
                           if v.get('flag') and v.get('author')}
        user_locs_map = {int(k): v for k, v in (locs_dict or {}).items()}
        return seen_ids, flagged_authors, user_locs_map

    # ---- New DB-backed per-user state helpers ----

    def _get_user_state(username, session):
        """
        Query user_report_state once for the given username.
        Returns (seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot).
        - seen_ids       : set of report_ids where hide=True
        - flagged_authors: set of flag_author strings where flag=True
        - user_locs_map  : {report_id: locations} where locations IS NOT NULL
        - added_ids      : set of report_ids where first_seen_at IS NOT NULL (admitted to sidebar)
        - new_ids        : set of report_ids where first_seen_at IS NOT NULL AND new=True (admitted but not yet clicked)
        - snapshot       : {str(report_id): {hide, flag, flag_author, added, new}} for clientside sync
        """
        rows = session.query(UserReportState).filter(
            UserReportState.username == username
        ).all()
        seen_ids       = set()
        flagged_authors = set()
        user_locs_map  = {}
        added_ids      = set()
        new_ids        = set()
        snapshot       = {}
        for row in rows:
            rid = row.report_id
            if row.hide:
                seen_ids.add(rid)
            if row.flag and row.flag_author:
                flagged_authors.add(row.flag_author)
            if row.locations is not None:
                user_locs_map[rid] = row.locations
            admitted = row.first_seen_at is not None
            if admitted:
                added_ids.add(rid)
                if row.new:
                    new_ids.add(rid)
            snapshot[str(rid)] = {
                'hide': bool(row.hide),
                'flag': bool(row.flag),
                'flag_author': row.flag_author or '',
                'added': admitted,
                'new': admitted and bool(row.new),
                'author': row.flag_author or '',
            }
        return seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, snapshot

    def _upsert_user_state(username, report_id, session, **kwargs):
        """
        INSERT or UPDATE a single user_report_state row.
        kwargs may include: hide, flag, flag_author, locations, first_seen_at, new
        Silently skips if report_id no longer exists in the reports table.
        """
        if not session.query(Report.id).filter(Report.id == report_id).scalar():
            return
        stmt = pg_insert(UserReportState).values(
            username=username,
            report_id=report_id,
            **kwargs,
        )
        update_cols = {k: stmt.excluded[k] for k in kwargs}
        stmt = stmt.on_conflict_do_update(
            constraint='uq_user_report',
            set_=update_cols,
        )
        session.execute(stmt)

    def _bulk_admit_reports(username, report_ids, session):
        """
        Bulk upsert: set first_seen_at=now() for all given report IDs for username.
        Rows that don't exist yet are created with defaults (hide=False, flag=False).
        """
        now = datetime.now(timezone.utc)
        for rid in report_ids:
            stmt = pg_insert(UserReportState).values(
                username=username,
                report_id=rid,
                first_seen_at=now,
                hide=False,
                flag=False,
            )
            stmt = stmt.on_conflict_do_update(
                constraint='uq_user_report',
                set_={'first_seen_at': now},
            )
            session.execute(stmt)

    def _filter_by_display(reports, loc_filter, seen_ids, flagged_authors, user_locs_map, vis):
        """Apply location and visibility (hide_seen/flagged/unflagged) filters in Python."""
        if vis.get('hide_seen'):
            reports = [r for r in reports if r.id not in seen_ids]
        if vis.get('hide_flagged'):
            reports = [r for r in reports if not r.author or r.author not in flagged_authors]
        if vis.get('hide_unflagged'):
            reports = [r for r in reports if r.author and r.author in flagged_authors]
        if loc_filter != 'all':
            filtered = []
            for r in reports:
                eff_locs = user_locs_map.get(r.id, r.locations) or []
                has_loc  = any('osm_id' in e for e in eff_locs)
                has_pend = not has_loc and bool(eff_locs)
                if loc_filter == 'localized' and not has_loc:
                    continue
                if loc_filter == 'pending' and not has_pend:
                    continue
                if loc_filter == 'unlocalized' and (has_loc or has_pend):
                    continue
                filtered.append(r)
            reports = filtered
        return reports

    def _render_sidebar(session, filter_platform, filter_event_type, filter_relevance_type, event_type_toggle, seen_ids=None, flagged_authors=None, user_locs_map=None, filter_visibility=None, added_ids=None, max_timestamp=None):
        from app.layout.map.sidebar import get_sidebar_content
        eff_platform, eff_events, eff_relevance = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
        return get_sidebar_content(
            filter_platform=eff_platform,
            filter_event_type=eff_events,
            filter_relevance_type=eff_relevance,
            loc_filter=event_type_toggle or 'all',
            seen_ids=seen_ids,
            flagged_authors=flagged_authors,
            user_locs_map=user_locs_map,
            added_ids=added_ids,
            max_timestamp=max_timestamp,
            **_vis_flags(filter_visibility),
        )

    def _build_dots(session, seen_ids=None, flagged_authors=None, user_locs_map=None,
                    filter_platform=None, filter_event_type=None,
                    filter_relevance_type=None, loc_filter='all',
                    hide_seen=False, hide_flagged=False, hide_unflagged=False,
                    new_ids=None, added_ids=None):
        q = session.query(Report).filter(Report.timestamp <= datetime.now(timezone.utc))
        if os.environ.get('DEMO_MODE') == '1':
            q = q.filter(Report.identifier.like('demo-%'))
        if filter_platform:
            from sqlalchemy import or_ as _or
            q = q.filter(_or(*[Report.platform.like(f'{p}%') for p in filter_platform]))
        if filter_event_type:
            q = q.filter(Report.event_type.in_(filter_event_type))
        if filter_relevance_type:
            q = q.filter(Report.relevance.in_(filter_relevance_type))
        if added_ids:
            q = q.filter(Report.id.in_(added_ids))
        reports = q.all()
        _seen_ids = seen_ids or set()
        _flagged = flagged_authors or set()
        if hide_seen:
            reports = [r for r in reports if r.id not in _seen_ids]
        if hide_flagged:
            reports = [r for r in reports if not r.author or r.author not in _flagged]
        if hide_unflagged:
            reports = [r for r in reports if r.author and r.author in _flagged]
        dots = []
        for r in reports:
            # location filter
            if loc_filter != 'all':
                effective = (user_locs_map or {}).get(r.id, r.locations) or []
                is_localized = any('osm_id' in l for l in effective)
                has_pending  = not is_localized and bool(effective)
                if loc_filter == 'localized' and not is_localized:
                    continue
                if loc_filter == 'pending' and not has_pending:
                    continue
                if loc_filter == 'unlocalized' and (is_localized or has_pending):
                    continue
            effective_locs = (user_locs_map or {}).get(r.id, r.locations) or []
            for loc in effective_locs:
                if 'osm_id' not in loc:
                    continue
                lat, lon = loc.get('lat'), loc.get('lon')
                if lat is None or lon is None:
                    continue
                dots.append({
                    'report_id': r.id,
                    'lat': lat,
                    'lon': lon,
                    'seen': r.id in (seen_ids or set()),
                    'new': r.id in (new_ids or set()),
                    'location_name': loc.get('name') or loc.get('mention') or '',
                    'location_display': loc.get('display_name') or '',
                    'text': (r.text or '')[:300],
                    'author': r.author or '',
                    'platform': r.platform or '',
                    'timestamp': r.timestamp.strftime('%H:%M %d.%m.%Y') if r.timestamp else '',
                    'event_type': r.event_type or '',
                    'relevance': r.relevance or '',
                    'url': r.url or '',
                })
        return dots

    # ---- Location picking: enter pick mode (add new) ----
    @app.callback(
        Output('location-pick-mode', 'data'),
        Input({'type': 'pick-location-button', 'index': ALL}, 'n_clicks'),
        prevent_initial_call=True,
    )
    def enter_pick_mode(n_clicks_list):
        if not ctx.triggered or all(n is None or n == 0 for n in n_clicks_list):
            raise PreventUpdate
        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        try:
            report_id = json.loads(triggered_id_str).get('index')
        except Exception:
            raise PreventUpdate
        return {'report_id': report_id, 'loc_index': None, 'mention': None}

    # ---- Location picking: enter pick mode (georeference existing) ----
    @app.callback(
        Output('location-pick-mode', 'data', allow_duplicate=True),
        Input({'type': 'georeference-location-button', 'report': ALL, 'loc': ALL}, 'n_clicks'),
        State('current-user', 'data'),
        prevent_initial_call=True,
    )
    def enter_georeference_mode(n_clicks_list, username):
        if not ctx.triggered or all(n is None or n == 0 for n in n_clicks_list):
            raise PreventUpdate
        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        try:
            id_dict = json.loads(triggered_id_str)
            report_id = id_dict.get('report')
            loc_index = id_dict.get('loc')
        except Exception:
            raise PreventUpdate
        engine, session = autoconnect_db()
        try:
            r = session.query(Report).filter(Report.id == report_id).first()
            effective_locs = r.locations if r else []
            if username:
                urs = session.query(UserReportState).filter_by(
                    username=username, report_id=report_id
                ).first()
                if urs and urs.locations is not None:
                    effective_locs = urs.locations
            effective_locs = effective_locs or []
            mention = ''
            if 0 <= loc_index < len(effective_locs):
                loc = effective_locs[loc_index]
                mention = loc.get('mention') or ''  # only the original surface form, never the resolved name
        finally:
            session.close()
            engine.dispose()
        return {'report_id': report_id, 'loc_index': loc_index, 'mention': mention}

    # ---- Location picking: cancel pick mode ----
    @app.callback(
        Output('location-pick-mode', 'data', allow_duplicate=True),
        Input('location-pick-cancel', 'n_clicks'),
        prevent_initial_call=True,
    )
    def cancel_pick_mode(_n):
        return None

    # ---- OSM search while in pick mode ----
    @app.callback(
        Output('location-search-data', 'data', allow_duplicate=True),
        Output('location-search-results', 'children'),
        Output('location-search-results', 'style'),
        Input('location-search-button', 'n_clicks'),
        Input('location-search-input', 'n_submit'),
        State('location-search-input', 'value'),
        State('location-pick-mode', 'data'),
        State('lang', 'data'),
        prevent_initial_call=True,
    )
    def search_osm_location(_btn, _submit, query, pick_mode, lang):
        if not pick_mode or not query or not query.strip():
            raise PreventUpdate
        try:
            nominatim_url = os.environ.get('NOMINATIM_URL', 'https://nominatim.openstreetmap.org').rstrip('/')
            resp = requests.get(
                f'{nominatim_url}/search',
                params={'q': query.strip(), 'format': 'json', 'limit': 7, 'polygon_geojson': 1},
                headers={'User-Agent': 'sems-digital-twin-map/1.0'},
                timeout=5,
            )
            results = resp.json()
        except Exception:
            results = []
        if not results:
            items = [html.Div(_t(lang or 'de', 'no_results'), style={'padding': '8px 12px', 'font-size': '11px', 'color': '#888'})]
            show_style = {**_results_hidden_style, 'display': 'block'}
            return [], items, show_style
        items = [
            html.Button(
                r.get('display_name', '')[:90],
                id={'type': 'osm-result-button', 'index': i},
                n_clicks=0,
                style={
                    'display': 'block', 'width': '100%', 'text-align': 'left',
                    'padding': '7px 12px', 'border': 'none', 'border-bottom': '1px solid #f0f0f0',
                    'background': 'none', 'cursor': 'pointer', 'font-size': '11px', 'color': '#333',
                },
            )
            for i, r in enumerate(results)
        ]
        show_style = {**_results_hidden_style, 'display': 'block'}
        return results, items, show_style

    # ---- Place location from OSM search result ----
    @app.callback(
        Output('location-pick-mode', 'data', allow_duplicate=True),
        Output('reports_list', 'children', allow_duplicate=True),
        Output('report-dots-data', 'data', allow_duplicate=True),
        Output('locations-changed', 'data', allow_duplicate=True),
        Input({'type': 'osm-result-button', 'index': ALL}, 'n_clicks'),
        State('location-search-data', 'data'),
        State('location-pick-mode', 'data'),
        State('current-user', 'data'),
        State('reports_dropdown_platform', 'value'),
        State('reports_dropdown_event_type', 'value'),
        State('reports_dropdown_relevance_type', 'value'),
        State('event_type_toggle', 'value'),
        State('locations-changed', 'data'),
        State('reports_filter_visibility', 'value'),
        State('sidebar-loaded-at', 'data'),
        prevent_initial_call=True,
    )
    def place_location_from_search(n_clicks_list, search_data, pick_mode, username,
                                   filter_platform, filter_event_type, filter_relevance_type, event_type_toggle, loc_rev,
                                   filter_visibility, loaded_at):
        if not username:
            raise PreventUpdate
        if not ctx.triggered or all(n is None or n == 0 for n in n_clicks_list):
            raise PreventUpdate
        if not pick_mode or not search_data:
            raise PreventUpdate
        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        try:
            result_index = json.loads(triggered_id_str).get('index')
        except Exception:
            raise PreventUpdate
        if result_index is None or result_index >= len(search_data):
            raise PreventUpdate

        selected = search_data[result_index]
        report_id = pick_mode.get('report_id') if isinstance(pick_mode, dict) else pick_mode
        loc_index = pick_mode.get('loc_index') if isinstance(pick_mode, dict) else None

        osm_type = selected.get('osm_type', 'node')
        osm_id = selected.get('osm_id')
        polygon = selected.get('geojson') or None
        new_loc = {
            'osm_id': f"{osm_type[0]}{osm_id}",
            'lat': float(selected['lat']),
            'lon': float(selected['lon']),
            'name': selected.get('display_name', '').split(',')[0].strip(),
            'display_name': selected.get('display_name', ''),
            'polygon': polygon,
        }
        if isinstance(pick_mode, dict) and pick_mode.get('mention'):
            new_loc['mention'] = pick_mode['mention']

        engine, session = autoconnect_db()
        try:
            r = session.query(Report).filter(Report.id == report_id).first()
            if r is None:
                raise PreventUpdate
            # Get current locations (user override or report default)
            urs = session.query(UserReportState).filter_by(username=username, report_id=report_id).first()
            current_locs = (urs.locations if urs and urs.locations is not None else r.locations) or []
            locs = list(current_locs)
            if loc_index is not None and 0 <= loc_index < len(locs):
                locs[loc_index] = {**locs[loc_index], **new_loc}
            else:
                locs.append(new_loc)
            _upsert_user_state(username, report_id, session, locations=locs)
            session.commit()

            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, _ = _get_user_state(username, session)
            eff_p, eff_e, eff_r = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
            sidebar = _render_sidebar(session, filter_platform, filter_event_type, filter_relevance_type, event_type_toggle,
                                      seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map,
                                      filter_visibility=filter_visibility, added_ids=added_ids, max_timestamp=loaded_at)
            dots = _build_dots(session, seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map,
                                filter_platform=eff_p, filter_event_type=eff_e, filter_relevance_type=eff_r,
                                loc_filter=event_type_toggle or 'all', new_ids=new_ids, added_ids=added_ids, **_vis_flags(filter_visibility))
            return None, sidebar, dots, (loc_rev or 0) + 1
        finally:
            session.close()
            engine.dispose()

    # ---- Location picking: show/hide overlay (server-side) ----
    _overlay_base_style = {
        'position': 'fixed', 'top': '112px', 'left': '50%', 'transform': 'translateX(-50%)',
        'zIndex': 1100, 'background': 'rgba(21,101,192,0.92)', 'color': '#fff',
        'padding': '10px 18px', 'border-radius': '8px', 'pointer-events': 'auto',
        'flex-direction': 'column', 'align-items': 'flex-start', 'gap': '0',
    }
    _results_hidden_style = {
        'display': 'none',
        'margin-top': '4px',
        'background': 'white', 'border': '1px solid #ddd', 'border-radius': '6px',
        'box-shadow': '0 4px 16px rgba(0,0,0,0.15)', 'width': '100%',
        'max-height': '240px', 'overflow-y': 'auto',
    }

    @app.callback(
        Output('location-pick-overlay', 'style'),
        Output('location-pick-overlay-text', 'children'),
        Output('location-search-input', 'value'),
        Output('location-search-results', 'style', allow_duplicate=True),
        Output('location-search-data', 'data', allow_duplicate=True),
        Input('location-pick-mode', 'data'),
        prevent_initial_call=True,
    )
    def update_pick_overlay(pick_mode):
        if not pick_mode:
            return {**_overlay_base_style, 'display': 'none'}, dash.no_update, '', _results_hidden_style, []
        mention = pick_mode.get('mention') if isinstance(pick_mode, dict) else None
        text = f'Click on the map to georeference "{mention}"' if mention else 'Click on the map to place a location'
        return {**_overlay_base_style, 'display': 'flex'}, text, dash.no_update, dash.no_update, dash.no_update

    # ---- Location picking: map click → save location ----
    @app.callback(
        Output('location-pick-mode', 'data', allow_duplicate=True),
        Output('reports_list', 'children', allow_duplicate=True),
        Output('report-dots-data', 'data', allow_duplicate=True),
        Output('locations-changed', 'data', allow_duplicate=True),
        Input('map', 'clickData'),
        State('location-pick-mode', 'data'),
        State('current-user', 'data'),
        State('reports_dropdown_platform', 'value'),
        State('reports_dropdown_event_type', 'value'),
        State('reports_dropdown_relevance_type', 'value'),
        State('event_type_toggle', 'value'),
        State('locations-changed', 'data'),
        State('reports_filter_visibility', 'value'),
        State('sidebar-loaded-at', 'data'),
        prevent_initial_call=True,
    )
    def place_location(click_data, pick_mode, username,
                       filter_platform, filter_event_type, filter_relevance_type, event_type_toggle, loc_rev,
                       filter_visibility, loaded_at):
        if not username or pick_mode is None or not click_data:
            raise PreventUpdate
        latlng = click_data.get('latlng', {})
        lat, lon = latlng.get('lat'), latlng.get('lng')
        if lat is None or lon is None:
            raise PreventUpdate

        report_id = pick_mode.get('report_id') if isinstance(pick_mode, dict) else pick_mode
        loc_index = pick_mode.get('loc_index') if isinstance(pick_mode, dict) else None

        engine, session = autoconnect_db()
        try:
            r = session.query(Report).filter(Report.id == report_id).first()
            if r is None:
                raise PreventUpdate
            urs = session.query(UserReportState).filter_by(username=username, report_id=report_id).first()
            current_locs = (urs.locations if urs and urs.locations is not None else r.locations) or []
            locs = list(current_locs)
            new_coords = {
                'osm_id': f'manual_{lat:.6f}_{lon:.6f}',
                'lat': lat,
                'lon': lon,
                'name': f'{lat:.4f}, {lon:.4f}',
            }
            if loc_index is not None and 0 <= loc_index < len(locs):
                locs[loc_index] = {**locs[loc_index], **new_coords}
            else:
                locs.append(new_coords)
            _upsert_user_state(username, report_id, session, locations=locs)
            session.commit()

            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, _ = _get_user_state(username, session)
            eff_p, eff_e, eff_r = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
            sidebar = _render_sidebar(session, filter_platform, filter_event_type, filter_relevance_type, event_type_toggle,
                                      seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map,
                                      filter_visibility=filter_visibility, added_ids=added_ids, max_timestamp=loaded_at)
            dots = _build_dots(session, seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map,
                                filter_platform=eff_p, filter_event_type=eff_e, filter_relevance_type=eff_r,
                                loc_filter=event_type_toggle or 'all', new_ids=new_ids, added_ids=added_ids, **_vis_flags(filter_visibility))
            return None, sidebar, dots, (loc_rev or 0) + 1
        finally:
            session.close()
            engine.dispose()

    # ---- Location removal ----
    @app.callback(
        Output('reports_list', 'children', allow_duplicate=True),
        Output('report-dots-data', 'data', allow_duplicate=True),
        Output('locations-changed', 'data', allow_duplicate=True),
        Input({'type': 'remove-location-button', 'report': ALL, 'loc': ALL}, 'n_clicks'),
        State('current-user', 'data'),
        State('reports_dropdown_platform', 'value'),
        State('reports_dropdown_event_type', 'value'),
        State('reports_dropdown_relevance_type', 'value'),
        State('event_type_toggle', 'value'),
        State('locations-changed', 'data'),
        State('reports_filter_visibility', 'value'),
        State('sidebar-loaded-at', 'data'),
        prevent_initial_call=True,
    )
    def remove_location(n_clicks_list, username,
                        filter_platform, filter_event_type, filter_relevance_type, event_type_toggle, loc_rev,
                        filter_visibility, loaded_at):
        if not username or not ctx.triggered or all(n is None or n == 0 for n in n_clicks_list):
            raise PreventUpdate
        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        try:
            id_dict = json.loads(triggered_id_str)
            report_id = id_dict.get('report')
            loc_index = id_dict.get('loc')
        except Exception:
            raise PreventUpdate
        if report_id is None or loc_index is None:
            raise PreventUpdate

        engine, session = autoconnect_db()
        try:
            r = session.query(Report).filter(Report.id == report_id).first()
            if r is None:
                raise PreventUpdate
            urs = session.query(UserReportState).filter_by(username=username, report_id=report_id).first()
            current_locs = (urs.locations if urs and urs.locations is not None else r.locations) or []
            locs = list(current_locs)
            if 0 <= loc_index < len(locs):
                locs.pop(loc_index)
            _upsert_user_state(username, report_id, session, locations=locs)
            session.commit()

            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, _ = _get_user_state(username, session)
            eff_p, eff_e, eff_r = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
            sidebar = _render_sidebar(session, filter_platform, filter_event_type, filter_relevance_type, event_type_toggle,
                                      seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map,
                                      filter_visibility=filter_visibility, added_ids=added_ids, max_timestamp=loaded_at)
            dots = _build_dots(session, seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map,
                                filter_platform=eff_p, filter_event_type=eff_e, filter_relevance_type=eff_r,
                                loc_filter=event_type_toggle or 'all', new_ids=new_ids, added_ids=added_ids, **_vis_flags(filter_visibility))
            return sidebar, dots, (loc_rev or 0) + 1
        finally:
            session.close()
            engine.dispose()

    # ---- Restore original locations ----
    @app.callback(
        Output('reports_list', 'children', allow_duplicate=True),
        Output('report-dots-data', 'data', allow_duplicate=True),
        Output('locations-changed', 'data', allow_duplicate=True),
        Input({'type': 'restore-locations-button', 'index': ALL}, 'n_clicks'),
        State('current-user', 'data'),
        State('reports_dropdown_platform', 'value'),
        State('reports_dropdown_event_type', 'value'),
        State('reports_dropdown_relevance_type', 'value'),
        State('event_type_toggle', 'value'),
        State('locations-changed', 'data'),
        State('reports_filter_visibility', 'value'),
        State('sidebar-loaded-at', 'data'),
        prevent_initial_call=True,
    )
    def restore_original_locations(n_clicks_list, username,
                                   filter_platform, filter_event_type, filter_relevance_type, event_type_toggle, loc_rev,
                                   filter_visibility, loaded_at):
        if not username or not ctx.triggered or all(n is None or n == 0 for n in n_clicks_list):
            raise PreventUpdate
        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        try:
            report_id = json.loads(triggered_id_str).get('index')
        except Exception:
            raise PreventUpdate
        if report_id is None:
            raise PreventUpdate

        eff_p, eff_e, eff_r = _normalize_filters(filter_platform, filter_event_type, filter_relevance_type)
        engine, session = autoconnect_db()
        try:
            # Clear user location override (set locations=None)
            _upsert_user_state(username, report_id, session, locations=None)
            session.commit()

            seen_ids, flagged_authors, user_locs_map, added_ids, new_ids, _ = _get_user_state(username, session)
            sidebar = _render_sidebar(session, filter_platform, filter_event_type, filter_relevance_type, event_type_toggle,
                                      seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map,
                                      filter_visibility=filter_visibility, added_ids=added_ids, max_timestamp=loaded_at)
            dots = _build_dots(session, seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map,
                                filter_platform=eff_p, filter_event_type=eff_e, filter_relevance_type=eff_r,
                                loc_filter=event_type_toggle or 'all', new_ids=new_ids, added_ids=added_ids, **_vis_flags(filter_visibility))
            return sidebar, dots, (loc_rev or 0) + 1
        finally:
            session.close()
            engine.dispose()

    # ---- Demo: reset button ----
    @app.callback(
        Output('reports_list', 'children', allow_duplicate=True),
        Output('user-state-snapshot', 'data', allow_duplicate=True),
        Output('sidebar-loaded-at', 'data', allow_duplicate=True),
        Input('demo-reset-button', 'n_clicks'),
        State('current-user', 'data'),
        State('reports_dropdown_platform', 'value'),
        State('reports_dropdown_event_type', 'value'),
        State('reports_dropdown_relevance_type', 'value'),
        State('event_type_toggle', 'value'),
        State('reports_filter_visibility', 'value'),
        State('lang', 'data'),
        prevent_initial_call=True,
    )
    def reset_demo(n_clicks, username, filter_platform, filter_event_type, filter_relevance_type,
                   event_type_toggle, filter_visibility, lang):
        if not n_clicks:
            raise PreventUpdate
        from data.build import seed_demo_data
        engine, session = autoconnect_db()
        try:
            seed_demo_data(session)
            # Admit the demo posts that are already current and rebuild the sidebar.
            demo_reports = session.query(Report).filter(
                Report.identifier.like('demo-%'),
                Report.timestamp <= datetime.now(timezone.utc),
            ).all()
            if username:
                _bulk_admit_reports(username, [r.id for r in demo_reports], session)
                session.commit()
                _, _, _, _, _, snapshot = _get_user_state(username, session)
            else:
                snapshot = {}
            sidebar = _build_sidebar_content(
                filter_platform, filter_event_type, filter_relevance_type,
                event_type_toggle, username=username, session=session,
                filter_visibility=filter_visibility, lang=lang or 'de',
            )
            # Use the earliest demo post timestamp as loaded_at so check_new_posts
            # correctly finds all future demo posts (spread over 5 min) as they arrive.
            if demo_reports:
                loaded_at = min(r.timestamp for r in demo_reports).isoformat()
            else:
                loaded_at = datetime.now(timezone.utc).isoformat()
            return sidebar, snapshot, loaded_at
        finally:
            session.close()
            engine.dispose()

    # ---- Persist filter state across page reloads ----
    @app.callback(
        Output('filter-state', 'data'),
        Input('reports_dropdown_platform', 'value'),
        Input('reports_dropdown_event_type', 'value'),
        Input('reports_dropdown_relevance_type', 'value'),
        Input('event_type_toggle', 'value'),
        Input('reports_filter_visibility', 'value'),
        Input('autoscroll-toggle', 'value'),
        prevent_initial_call=True,
    )
    def save_filter_state(platform, event_type, relevance, loc_filter, visibility, autoscroll):
        return {
            'platform': platform,
            'event_type': event_type,
            'relevance': relevance,
            'loc_filter': loc_filter,
            'visibility': visibility,
            'autoscroll': autoscroll,
        }

    @app.callback(
        Output('reports_dropdown_platform', 'value'),
        Output('reports_dropdown_event_type', 'value'),
        Output('reports_dropdown_relevance_type', 'value'),
        Output('event_type_toggle', 'value'),
        Output('reports_filter_visibility', 'value'),
        Output('autoscroll-toggle', 'value'),
        Input('current-user', 'data'),
        State('filter-state', 'data'),
    )
    def restore_filter_state(username, data):
        if not data:
            raise PreventUpdate
        all_platforms = list(get_sidebar_dropdown_platform_values())
        return (
            data.get('platform', all_platforms),
            data.get('event_type', [e for e in ALL_EVENT_TYPES if e != 'Irrelevant']),
            data.get('relevance', list(ALL_RELEVANCE_TYPES)),
            data.get('loc_filter', 'all'),
            data.get('visibility', ['show_flagged', 'show_unflagged']),
            data.get('autoscroll', []),
        )

    # ---- Filter counts ----
    @app.callback(
        Output({'type': 'event-chip', 'index': ALL}, 'children'),
        Output('reports_dropdown_platform', 'options'),
        Output('reports_dropdown_relevance_type', 'options'),
        Input('sidebar-loaded-at', 'data'),
        Input('interval_refresh_reports', 'n_intervals'),
        State('current-user', 'data'),
        State({'type': 'event-chip', 'index': ALL}, 'id'),
        State('lang', 'data'),
    )
    def update_filter_counts(_loaded_at, _n, username, chip_ids, lang):
        from sqlalchemy import func as sqlfunc
        if not username:
            raise PreventUpdate
        engine, session = autoconnect_db()
        try:
            # Count ALL current posts (admitted + pending banner posts)
            filters = [Report.timestamp <= datetime.now(timezone.utc)]
            if os.environ.get('DEMO_MODE') == '1':
                filters.append(Report.identifier.like('demo-%'))

            et_counts = dict(
                session.query(Report.event_type, sqlfunc.count(Report.id))
                .filter(*filters).group_by(Report.event_type).all()
            )
            raw_plat = session.query(Report.platform, sqlfunc.count(Report.id)) \
                .filter(*filters).group_by(Report.platform).all()
            rel_counts = dict(
                session.query(Report.relevance, sqlfunc.count(Report.id))
                .filter(*filters).group_by(Report.relevance).all()
            )

            plat_counts = {}
            for plat, cnt in raw_plat:
                key = 'rss' if str(plat).startswith('rss') else plat
                plat_counts[key] = plat_counts.get(key, 0) + cnt

            _lg = lang or 'de'
            chip_children = [
                [_t(_lg, f"et_{cid['index']}"), html.Span(f" {et_counts.get(cid['index'], 0)}", className='chip-count')]
                for cid in chip_ids
            ]
            all_platforms = list(get_sidebar_dropdown_platform_values())
            plat_options = [
                {'label': f'{p} ({plat_counts.get(p, 0)})', 'value': p}
                for p in all_platforms
            ]
            rel_options = [
                {'label': f'{_t(_lg, "rel_" + r)} ({rel_counts.get(r, 0)})', 'value': r}
                for r in ALL_RELEVANCE_TYPES
            ]
            return chip_children, plat_options, rel_options
        finally:
            session.close()
            engine.dispose()

    # Visibility counts derived from snapshot (no DB round-trip needed)
    app.clientside_callback(
        """
        function(snapshot) {
            if (!snapshot) return window.dash_clientside.no_update;
            var vals = Object.values(snapshot);
            var hidden    = vals.filter(function(s) { return s.added && s.hide; }).length;
            var flagged   = vals.filter(function(s) { return s.added && s.flag; }).length;
            var unflagged = vals.filter(function(s) { return s.added && !s.flag; }).length;
            return [
                {label: _t('show_hidden',   'Show hidden')   + ' (' + hidden    + ')', value: 'show_hidden'},
                {label: _t('show_flagged',  'Flagged')       + ' (' + flagged   + ')', value: 'show_flagged'},
                {label: _t('show_unflagged','Unflagged')     + ' (' + unflagged + ')', value: 'show_unflagged'},
            ];
        }
        """,
        Output('reports_filter_visibility', 'options'),
        Input('user-state-snapshot', 'data'),
    )

    # ---- Event-type filter chips ----
    # Chip click → update hidden checklist value (handles shift+click solo mode)
    app.clientside_callback(
        """
        function(n_clicks_list, current_values, all_types) {
            var ctx = dash_clientside.callback_context;
            if (!ctx.triggered || !ctx.triggered.length) return dash_clientside.no_update;
            var prop_id = ctx.triggered[0].prop_id;
            var match = prop_id.match(/"index":"([^"]+)"/);
            if (!match) return dash_clientside.no_update;
            var clicked = match[1];

            var selected = current_values ? current_values.slice() : all_types.slice();

            if (window._shiftPressed) {
                // Solo mode: if already the only one selected → restore all non-Irrelevant
                var isSolo = selected.length === 1 && selected[0] === clicked;
                return isSolo
                    ? all_types.filter(function(e) { return e !== 'Irrelevant'; })
                    : [clicked];
            } else {
                var idx = selected.indexOf(clicked);
                if (idx >= 0) { selected.splice(idx, 1); } else { selected.push(clicked); }
                return selected;
            }
        }
        """,
        Output('reports_dropdown_event_type', 'value', allow_duplicate=True),
        Input({'type': 'event-chip', 'index': ALL}, 'n_clicks'),
        State('reports_dropdown_event_type', 'value'),
        State('event-types-all', 'data'),
        prevent_initial_call=True,
    )

    # Checklist value → chip classNames (keeps chips in sync with restore/reset)
    app.clientside_callback(
        """
        function(values, ids) {
            if (!values || !ids) return ids.map(function() { return 'filter-chip'; });
            return ids.map(function(id) {
                return values.indexOf(id.index) >= 0 ? 'filter-chip filter-chip-active' : 'filter-chip';
            });
        }
        """,
        Output({'type': 'event-chip', 'index': ALL}, 'className'),
        Input('reports_dropdown_event_type', 'value'),
        State({'type': 'event-chip', 'index': ALL}, 'id'),
    )
