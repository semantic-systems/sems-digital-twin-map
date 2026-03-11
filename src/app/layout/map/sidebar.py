import json
import os
from datetime import datetime, timedelta

from dash import Dash, html, dcc, Output, Input, State, callback_context, MATCH, ALL
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

from data.connect import autoconnect_db
from data.model import Report



# the path to the config file that contains the platform specific information
SIDEBAR_CONFIG_PATH = 'src/app/layout/map/sidebar_config.json'

def get_platform_config(platform):
    """
    Get the configuration for a specific platform.
    """
    with open(SIDEBAR_CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
        return config[platform]

def format_report(report: Report, seen_ids=None, flagged_authors=None, user_locs_map=None) -> html.Li:
    platform = report.platform
    if platform.startswith('rss'):
        platform = 'rss'
    platform_config = get_platform_config(platform)
    text = report.text.replace('\n', ' ')

    platform_name = platform_config['name']
    timestamp = report.timestamp.strftime('%H:%M %d.%m.%Y')
    event_type = report.event_type
    relevance = report.relevance
    is_seen    = (report.id in seen_ids) if seen_ids else False
    is_flagged = ((report.author or '') in flagged_authors) if flagged_authors else False

    author = getattr(report, 'author', '') or ''
    effective_locations = (user_locs_map or {}).get(report.id, report.locations)
    has_user_override = user_locs_map is not None and report.id in user_locs_map

    is_localized = any('osm_id' in loc for loc in (effective_locations or []))
    has_pending  = not is_localized and bool(effective_locations)   # has locations but none georeferenced

    if platform == 'rss':
        feed_name = report.platform.split('/')[1]
        descriptor_text = f'{feed_name} · {event_type} · {relevance} · {timestamp}'
    else:
        descriptor_text = f'{platform_name} · {event_type} · {relevance} · {timestamp}'

    relevance_color_map = {
        "none": "#e0e0e0",
        "low": "#ffcccc",
        "medium": "#ff8a80",
        "high": "#cc0000",
    }
    bg_color = relevance_color_map.get(relevance, "#e0e0e0")

    seen_btn_label = "👁 Seen" if is_seen else "👁"
    seen_btn_title = "Mark as unseen" if is_seen else "Mark as seen"
    seen_btn_style = {
        'font-size': '11px',
        'padding': '2px 7px',
        'cursor': 'pointer',
        'border-radius': '4px',
        'transition': 'all 0.15s',
        'white-space': 'nowrap',
        'border': '1px solid #a5d6a7' if is_seen else '1px solid #ddd',
        'background': '#e8f5e9' if is_seen else '#fafafa',
        'color': '#2e7d32' if is_seen else '#888',
        'font-weight': 'bold' if is_seen else 'normal',
    }

    entry_opacity = 0.5 if is_seen else 1.0

    return html.Li(
        children=[
            html.Button(
                [
                    html.Span(
                        text,
                        style={
                            "font-weight": "bold",
                            "font-size": "10px",
                            "line-height": "1.4",
                            "display": "-webkit-box",
                            "-webkit-box-orient": "vertical",
                            "-webkit-line-clamp": "5",
                            "margin-bottom": "2px",
                            "white-space": "normal",
                            "word-wrap": "break-word",
                            "overflow": "hidden",
                            "text-overflow": "ellipsis",
                            "max-width": "100%",
                        }
                    ),
                    html.P(
                        [
                            html.Span(
                                '📍 ' if is_localized else ('◎ ' if has_pending else '· '),
                                title='Georeferenced' if is_localized else ('Locations pending georeferencing' if has_pending else 'No locations'),
                                style={
                                    'color': '#43a047' if is_localized else ('#e65100' if has_pending else '#bdbdbd'),
                                    'font-size': '9px',
                                    'margin-right': '2px',
                                }
                            ),
                            (f'@{author} · ' if author else '') + descriptor_text,
                        ],
                        style={
                            'font-size': '9px',
                            'color': '#888',
                            'margin': '0',
                        }
                    )
                ],
                id={'type': 'report-entry', 'index': report.id},
                n_clicks=0,
                style={
                    "background": "none",
                    "border": "none",
                    "width": "100%",
                    "textAlign": "left",
                    "cursor": "pointer",
                    "padding": "0",
                    "display": "inline-block",
                    "verticalAlign": "top",
                }
            ),
            html.Div(
                children=[
                    html.A(
                        "↗ Open",
                        href=report.url,
                        target="_blank",
                        rel="noopener noreferrer",
                        title="Open original post",
                        style={
                            'font-size': '9px',
                            'color': '#1976d2',
                            'text-decoration': 'none',
                        }
                    ),
                    html.Button(
                        seen_btn_label,
                        id={'type': 'seen-button', 'index': report.id},
                        title=seen_btn_title,
                        n_clicks=0,
                        style=seen_btn_style,
                    ),
                    html.Button(
                        '🚩' if is_flagged else '🏳',
                        id={'type': 'flag-button', 'index': report.id},
                        title='Unflag author' if is_flagged else 'Flag author',
                        n_clicks=0,
                        style={
                            'font-size': '11px',
                            'padding': '2px 7px',
                            'cursor': 'pointer',
                            'border-radius': '4px',
                            'transition': 'all 0.15s',
                            'white-space': 'nowrap',
                            'border': '1px solid #e65100' if is_flagged else '1px solid #ddd',
                            'background': '#fff3e0' if is_flagged else '#fafafa',
                            'color': '#e65100' if is_flagged else '#888',
                            'font-weight': 'bold' if is_flagged else 'normal',
                        },
                    ),
                ],
                style={'display': 'flex', 'gap': '8px', 'align-items': 'center', 'margin-top': '4px'}
            ),
            html.Div(
                children=[
                    *[
                        html.Span(
                            [
                                html.Button(
                                    ['◌ ', html.I(loc.get('mention') or loc.get('name') or '')],
                                    id={'type': 'georeference-location-button', 'report': report.id, 'loc': i},
                                    n_clicks=0,
                                    title='Click to georeference this location on the map',
                                    style={
                                        'font-size': '9px', 'padding': '0', 'border': 'none',
                                        'background': 'transparent', 'cursor': 'pointer',
                                        'color': '#757575', 'font-style': 'italic',
                                        'text-decoration': 'underline dotted',
                                    },
                                ),
                                html.Button(
                                    '✕',
                                    id={'type': 'remove-location-button', 'report': report.id, 'loc': i},
                                    n_clicks=0,
                                    title='Remove location',
                                    style={
                                        'font-size': '9px', 'padding': '0 3px', 'margin-left': '3px',
                                        'cursor': 'pointer', 'border': 'none', 'background': 'transparent',
                                        'color': '#888', 'line-height': '1',
                                    },
                                ),
                            ],
                            style={
                                'font-size': '9px', 'border-radius': '3px',
                                'padding': '1px 4px', 'margin-right': '3px', 'white-space': 'nowrap',
                                'display': 'inline-flex', 'align-items': 'center',
                                'background': '#fdecea', 'border': '1px dashed #e57373', 'color': '#c62828',
                            },
                        ) if 'osm_id' not in loc else html.Span(
                            [
                                html.Button(
                                    loc.get('mention') or loc.get('name') or f"{loc.get('lat', 0):.4f}, {loc.get('lon', 0):.4f}",
                                    id={'type': 'georeference-location-button', 'report': report.id, 'loc': i},
                                    n_clicks=0,
                                    title='Click to reassign location on the map',
                                    style={
                                        'font-size': '9px', 'padding': '0', 'border': 'none',
                                        'background': 'transparent', 'cursor': 'pointer',
                                        'color': 'inherit', 'text-decoration': 'underline dotted',
                                    },
                                ),
                                html.Button(
                                    '✕',
                                    id={'type': 'remove-location-button', 'report': report.id, 'loc': i},
                                    n_clicks=0,
                                    title='Remove location',
                                    style={
                                        'font-size': '9px', 'padding': '0 3px', 'margin-left': '3px',
                                        'cursor': 'pointer', 'border': 'none', 'background': 'transparent',
                                        'color': '#888', 'line-height': '1',
                                    },
                                ),
                            ],
                            title=loc.get('display_name') or loc.get('name') or '',
                            style={
                                'font-size': '9px', 'border-radius': '3px',
                                'padding': '1px 4px', 'margin-right': '3px', 'white-space': 'nowrap',
                                'display': 'inline-flex', 'align-items': 'center',
                                'background': '#e8f5e9', 'border': '1px solid #81c784', 'color': '#2e7d32',
                            },
                        )
                        for i, loc in enumerate(effective_locations or [])
                    ],
                    html.Button(
                        '📍 Add',
                        id={'type': 'pick-location-button', 'index': report.id},
                        n_clicks=0,
                        title='Click to place a location on the map',
                        style={
                            'font-size': '9px', 'padding': '1px 6px', 'cursor': 'pointer',
                            'border-radius': '3px', 'border': '1px solid #90caf9',
                            'background': '#e3f2fd', 'color': '#1565c0',
                        },
                    ),
                    *(
                        [html.Button(
                            '↩ Restore',
                            id={'type': 'restore-locations-button', 'index': report.id},
                            n_clicks=0,
                            title='Restore originally detected locations',
                            style={
                                'font-size': '9px', 'padding': '1px 6px', 'cursor': 'pointer',
                                'border-radius': '3px', 'border': '1px solid #ce93d8',
                                'background': '#f3e5f5', 'color': '#6a1b9a',
                            },
                        )]
                        if has_user_override else []
                    ),
                ],
                style={'display': 'flex', 'flex-wrap': 'wrap', 'gap': '3px', 'align-items': 'center', 'margin-top': '5px'},
            ),
        ],
        style={
            'margin-bottom': '8px',
            'border-left': '4px solid ' + ('#43a047' if is_localized else ('#e65100' if has_pending else '#bdbdbd')),
            'border-right': f'4px solid {bg_color}',
            'border-radius': '4px',
            'padding': '6px 6px 4px 8px',
            'display': 'flex',
            'flex-direction': 'column',
            'alignItems': 'flex-start',
            'background': '#fafafa',
            'opacity': str(entry_opacity),
            'transition': 'opacity 0.2s',
            'outline': '2px solid #e65100' if is_flagged else 'none',
        }
    )

def format_reports(reports: list, n=25, seen_ids=None, flagged_authors=None, user_locs_map=None) -> list:
    """
    Formats the reports into a list of html elements that can be displayed in the sidebar.
    """

    # if the list is empty, return a placeholder
    if len(reports) == 0:
        return [
            html.Li(
                html.I('No reports available.'),
                style={
                    'color': 'gray',
                    'min-height': '50px',
                    'padding-top': '25px',
                    'text-align': 'center'
                }
            )
        ]

    return [format_report(report, seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map) for report in reports[:n]]

def get_sidebar_content(n=25, filter_platform=None, filter_event_type=None, filter_relevance_type=None, loc_filter='all', seen_ids=None, flagged_authors=None, user_locs_map=None):
    """
    Returns the n most recent posts from the reports server (posts.json).
    You can also filter by platform, event type, and relevance type(s).
    loc_filter: 'all' | 'localized' | 'pending' | 'unlocalized'
    seen_ids: set of report ids marked as seen (from browser localStorage)
    flagged_authors: set of author strings flagged (from browser localStorage)
    user_locs_map: dict mapping report_id -> [loc, ...] (from browser localStorage)
    """
    engine, session = autoconnect_db()
    filter_arguments = []

    if filter_platform:
        filter_arguments.append(Report.platform.like(f'{filter_platform}%'))

    if filter_event_type:
        # Handle multiple event types
        if isinstance(filter_relevance_type, list):
            filter_arguments.append(Report.event_type.in_(filter_event_type))
        else:
            filter_arguments.append(Report.event_type == filter_event_type)

    if filter_relevance_type:
        # Handle multiple relevance types
        if isinstance(filter_relevance_type, list):
            filter_arguments.append(Report.relevance.in_(filter_relevance_type))
        else:
            filter_arguments.append(Report.relevance == filter_relevance_type)

    # Only show reports with timestamps up to now (hides future-dated demo reports)
    filter_arguments.append(Report.timestamp <= datetime.utcnow())

    # In demo mode, only show demo-seeded reports (guards against server_reports re-inserting real ones)
    if os.environ.get('DEMO_MODE') == '1':
        filter_arguments.append(Report.identifier.like('demo-%'))

    query = session.query(Report)
    if filter_arguments:
        query = query.filter(*filter_arguments)

    reports = query.order_by(Report.timestamp.desc()).all()

    session.close()

    seen_ids = seen_ids or set()
    flagged_authors = flagged_authors or set()
    user_locs_map = user_locs_map or {}

    if loc_filter == 'all':
        return format_reports(reports, n, seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map)

    filtered_reports = []
    for report in reports:
        effective_locs = user_locs_map.get(report.id, report.locations)
        has_location = any('osm_id' in e for e in (effective_locs or []))
        has_pending = not has_location and bool(effective_locs)
        if loc_filter == 'localized' and not has_location:
            continue
        if loc_filter == 'pending' and not has_pending:
            continue
        if loc_filter == 'unlocalized' and (has_location or has_pending):
            continue
        filtered_reports.append(report)

    return format_reports(filtered_reports, n, seen_ids=seen_ids, flagged_authors=flagged_authors, user_locs_map=user_locs_map)

def get_sidebar_dropdown_platform_values():
    """
    Returns the list of names of platforms in the config
    """

    # get all the platforms from the config
    with open(SIDEBAR_CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
        platforms = config.keys()

    return list(platforms)

ALL_EVENT_TYPES = [
    'Irrelevant',
    'Menschen betroffen',
    'Warnungen & Hinweise',
    'Evakuierungen & Umsiedlungen',
    'Spenden & Freiwillige',
    'Infrastruktur-Schäden',
    'Verletzte & Tote',
    'Vermisste & Gefundene',
    'Bedarfe & Anfragen',
    'Einsatzmaßnahmen',
    'Mitgefühl & Unterstützung',
    'Sonstiges',
]

ALL_RELEVANCE_TYPES = ['high', 'medium', 'low', 'none']

def get_sidebar_dropdown_event_type_values():
    return ALL_EVENT_TYPES

def get_sidebar_dropdown_relevance_type_values():
    return ALL_RELEVANCE_TYPES