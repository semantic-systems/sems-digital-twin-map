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
    """
    Format a single report into a html element that can be displayed in the sidebar.
    """

    # get the platform and config
    platform = report.platform                  # internal name, i.e. 'bluesky'

    if platform.startswith('rss'):
        platform = 'rss'

    platform_config = get_platform_config(platform)

    # get the headline and url
    text = report.text
    url = report.url

    # format the text and shorten it if it is too long
    text = text.replace('\n', ' ')
    if len(text) > 100:
        text = text[:100] + '...'

    platform_name = platform_config['name']     # display name, i.e. 'Bluesky'
    color = platform_config['color']            # color of the platform, i.e. #1185FE
    timestamp = report.timestamp.strftime('%H:%M %d.%m.%Y')
    event_type = report.event_type

    # build the desciptor
    if platform == 'rss':
        # if the platform is rss, we dont want to show 'rss', but the news feed name
        feed_name = report.platform.split('/')[1]
        descriptor_text = f'{feed_name} - {event_type} - {timestamp}'
    else:
        descriptor_text = f'{platform_name} - {event_type} - {timestamp}'

    return html.Li(
            html.A(
                children=[
                    text,
                    html.P(
                        descriptor_text,
                        style={
                            'font-size': '10px',
                            'color': 'gray'
                        }
                    )
                ],
                href=url,
                target='_blank',
                rel='noopener noreferrer'
            ),
            style={
                'margin-bottom': '10px',
                'border-left': f'5px solid {color}',
                'border-radius': '3px',
                'padding-left': '5px',
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

def get_sidebar_content(n=25, filter_platform=None, filter_event_type=None):
    """
    Returns the n most recent posts from the reports server (posts.json).
    You can also filter by platform and event type.
    """

    # get all Reports from the database where the platform==filter_platform and the event_type==filter_event_type
    engine, session = autoconnect_db()

    if filter_platform and filter_event_type:
        reports = session.query(Report).filter(Report.platform.like(f'{filter_platform}%'), Report.event_type == filter_event_type).order_by(Report.timestamp.desc()).all()
    elif filter_platform:
        reports = session.query(Report).filter(Report.platform.like(f'{filter_platform}%')).order_by(Report.timestamp.desc()).all()
    elif filter_event_type:
        reports = session.query(Report).filter(Report.event_type == filter_event_type).order_by(Report.timestamp.desc()).all()
    else:
        reports = session.query(Report).order_by(Report.timestamp.desc()).all()

    session.close()

    return format_reports(reports, n)

def get_sidebar_dropdown_platform_values():

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