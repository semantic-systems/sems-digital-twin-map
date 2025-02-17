import json
from datetime import datetime, timedelta

from dash import Dash, html, dcc, Output, Input, State, callback_context, MATCH, ALL
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

import subprocess

# the path of the output file the social media extractor creates
# posts are loaded from this file
POST_SAVE_PATH = 'data/posts.json'

# the path to the config file that contains the platform specific information
SIDEBAR_CONFIG_PATH = 'src/app/layout/map/sidebar_config.json'

# this class is used to load and order the data from the output file
class PostLoader:
    def __init__(self, path_posts, path_config):
        self.data = self.load(path_posts)
        self.config = self.load(path_config)

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def order_by_date(self, reverse=True, platform=None):
        """Returns a copy of posts ordered by timestamp, latest first by default."""

        # filter by platform
        posts_platform = self.filter_by_platform(platform)

        return sorted(posts_platform, key=lambda x: datetime.fromisoformat(x['timestamp']), reverse=reverse)
    
    def order_by_platform(self, reverse=False):
        """Returns a copy of posts ordered alphabetically by platform."""
        return sorted(self.data, key=lambda x: x['platform'].lower())
    
    def get_platforms(self):
        """Returns a list of all platforms in the data."""
        platforms = list(set(post['platform'] for post in self.data))
        return platforms
    
    def filter_by_platform(self, platform):
        """
        Get all posts from a specific platform.
        """
        if platform is None:
            # return all posts
            posts_platform = self.data
        else:
            # iterate and keep only posts from the target platform
            posts_platform = []
            for post in self.data:
                if post['platform'] == platform:
                    posts_platform.append(post)
        
        return posts_platform
    
    def __len__(self):
        return len(self.data)
    
    def format_post_html(self, post):

        # get the platform and config
        platform = post['platform']
        platform_config = self.config[platform]

        # get the headline and url
        text_field = platform_config['text_field']
        text  = post.get(text_field, 'Error: No text found')
        url = post.get('url', '#')

        # format the text and shorten it if it is too long
        text = text.replace('\n', ' ')
        if len(text) > 100:
            text = text[:100] + '...'

        # get the formatting of the platform
        platform_name = platform_config['name']
        color = platform_config['color']
        timestamp = post['timestamp']
        timestamp = datetime.fromisoformat(timestamp).strftime('%H:%M %d.%m.%Y')

        # build the desciptor
        if platform == 'rss':
            # if the platform is rss, we dont want to show 'rss', but the news feed name
            feed_name = post.get('feed', 'Unknown Feed')
            descriptor_text = f'{feed_name} - {timestamp}'
        else:
            descriptor_text = f'{platform_name} - {timestamp}'

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
    
    def format_posts_html(self, posts, n=25):
        return [self.format_post_html(post) for post in posts[:n]]
    
def get_sidebar_content(n=25, order_by='date', platform=None):
    post_loader = PostLoader(POST_SAVE_PATH, SIDEBAR_CONFIG_PATH)

    if order_by == 'date':
        posts = post_loader.order_by_date(platform=platform)
    elif order_by == 'platform':
        posts = post_loader.order_by_platform(platform=platform)
    else:
        raise ValueError(f"Invalid order_by value: {order_by}. Can be 'date' or 'platform'.")

    return post_loader.format_posts_html(posts)

def get_sidebar_dropdown_values():
    post_loader = PostLoader(POST_SAVE_PATH, SIDEBAR_CONFIG_PATH)

    return post_loader.get_platforms()