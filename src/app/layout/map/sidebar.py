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

    if platform == 'rss':
        feed_name = report.platform.split('/')[1]
        descriptor_text = f'{feed_name} - {event_type} - {relevance} - {timestamp}'
    else:
        descriptor_text = f'{platform_name} - {event_type} - {relevance} - {timestamp}'

    color_map = {
        "none": "#ffffff",  # white
        "low": "#ffcccc",  # light red
        "medium": "#ff6666",  # medium red
        "high": "#cc0000"  # dark red
    }

    bg_color = color_map.get(relevance, "#ffffff")

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
                            "display": "-webkit-box",  # enables flex-like box model
                            "-webkit-box-orient": "vertical",  # sets vertical stacking
                            "-webkit-line-clamp": "5",  # limits to 5 lines
                            "margin-bottom": "4px",
                            "white-space": "normal",     # <-- allow line breaks
                            "word-wrap": "break-word",   # <-- break long words if needed
                            "overflow": "hidden",
                            "text-overflow": "ellipsis",
                            "max-width": "100%",  # or a fixed width, e.g. "600px"
                        }
                    ),
                    html.P(
                        descriptor_text,
                        style={
                            'font-size': '10px',
                            'color': 'gray',
                            'margin': '0'
                        }
                    )
                ],
                id={'type': 'report-entry', 'index': report.id},
                n_clicks=0,
                # Remove button styling except for pointer & alignment—looks like a flat Div
                style={
                    "background": "none",
                    "border": "none",
                    "width": "calc(100% - 30px)",  # leaves space for the icon
                    "textAlign": "left",
                    "cursor": "pointer",
                    "padding": "0",
                    "display": "inline-block",
                    "verticalAlign": "top"
                }
            ),
            html.A(
                "[Link]",
                href=report.url,
                target="_blank",
                rel="noopener noreferrer",
                title="Open original post",
                style={
                    'font-size': '18px',
                    'color': '#666',
                    'margin-left': '6px',
                    'text-decoration': 'none',
                    'verticalAlign': 'top',
                    'display': 'inline-block'
                }
            )
        ],
        style={
            'margin-bottom': '10px',
            'border-left': f'5px solid {color}',
            'border-right': f'5px solid {bg_color}',
            'border-radius': '3px',
            'padding-left': '5px',
            'display': 'flex',
            'alignItems': 'flex-start',
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

def get_sidebar_content(n=25, filter_platform=None, filter_event_type=None, filter_relevance_type=None):
    """
    Returns the n most recent posts from the reports server (posts.json).
    You can also filter by platform, event type, and relevance type(s).
    """
    engine, session = autoconnect_db()
    filter_arguments = []

    if filter_platform:
        filter_arguments.append(Report.platform.like(f'{filter_platform}%'))

    if filter_event_type:
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

    return format_reports(reports, n)

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