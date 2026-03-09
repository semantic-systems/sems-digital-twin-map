import json
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

def format_report(report: Report) -> html.Li:
    platform = report.platform
    if platform.startswith('rss'):
        platform = 'rss'
    platform_config = get_platform_config(platform)
    text = report.text.replace('\n', ' ')

    platform_name = platform_config['name']
    color = platform_config['color']
    timestamp = report.timestamp.strftime('%H:%M %d.%m.%Y')
    event_type = report.event_type
    relevance = report.relevance
    is_seen = bool(getattr(report, 'seen', False))

    author = getattr(report, 'author', '') or ''

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
                        (f'@{author} · ' if author else '') + descriptor_text,
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
                ],
                style={'display': 'flex', 'gap': '8px', 'align-items': 'center', 'margin-top': '4px'}
            )
        ],
        style={
            'margin-bottom': '8px',
            'border-left': f'4px solid {color}',
            'border-right': f'4px solid {bg_color}',
            'border-radius': '4px',
            'padding': '6px 6px 4px 8px',
            'display': 'flex',
            'flex-direction': 'column',
            'alignItems': 'flex-start',
            'background': '#fafafa' if not is_seen else '#f5f5f5',
            'opacity': str(entry_opacity),
            'transition': 'opacity 0.2s',
        }
    )

def format_reports(reports: list, n=25) -> list:
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

    return [format_report(report) for report in reports[:n]]

def get_sidebar_content(n=25, filter_platform=None, filter_event_type=None, filter_relevance_type=None, localized=True):
    """
    Returns the n most recent posts from the reports server (posts.json).
    You can also filter by platform, event type, and relevance type(s).
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

    query = session.query(Report)
    if filter_arguments:
        query = query.filter(*filter_arguments)

    reports = query.order_by(Report.timestamp.desc()).all()
    session.close()

    filtered_reports = []
    for report in reports:
        geolinked_entities = report.locations
        geolinked_entities = [entity for entity in geolinked_entities if "osm_id" in entity]
        if localized and len(geolinked_entities) == 0:
            continue
        elif not localized and len(geolinked_entities) > 0:
            continue
        filtered_reports.append(report)

    return format_reports(filtered_reports, n)

def get_sidebar_dropdown_platform_values():
    """
    Returns the list of names of platforms in the config
    """

    # get all the platforms from the config
    with open(SIDEBAR_CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
        platforms = config.keys()

    return list(platforms)

def get_sidebar_dropdown_event_type_values():

    # get the event_types of all Reports in the database
    engine, session = autoconnect_db()
    event_types = session.query(Report.event_type).distinct().all()
    event_types = [event_type[0] for event_type in event_types]

    session.close()

    return event_types

def get_sidebar_dropdown_relevance_type_values():

    # get the event_types of all Reports in the database
    engine, session = autoconnect_db()
    event_types = session.query(Report.relevance).distinct().all()
    event_types = [event_type[0] for event_type in event_types]

    session.close()

    return event_types