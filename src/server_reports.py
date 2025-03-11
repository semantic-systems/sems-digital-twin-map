import requests
import time
from datetime import datetime, timedelta
from data.connect import autoconnect_db
from data.model import Report

import random   # can be removed later

# how long to wait between requests (in seconds)
REQUEST_DELAY = 60 * 60 * 6    # 6 hours

# how long to wait before timing out a request (in seconds)
TIMEOUT_DELAY = 300            # 5 minutes

# set to True to print more information
VERBOSE = True

# user agent for the requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# the API URL
API_URL = 'http://python-social-media-retriever-api:5000/search'

# what text to use from posts from each platform
TEXT_FIELD = {
    "bluesky": "text",
    "mastodon": "text",
    "reddit": "title",
    "youtube": "title",
    "twitter": "text",
    "rss": "title"
}

# the search parameters
SEARCH_QUERY = 'hamburg sturm'
SEARCH_LIMIT = 25
SEARCH_SUBREDDITS = ['hamburg', 'de']
SEARCH_PLATFORMS = ['mastodon', 'bluesky', 'reddit', 'youtube', 'rss']
SEARCH_MANDATORY_KEYWORDS = ['hamburg']
SEARCH_OPTIONAL_KEYWORDS = ['sturm', 'storm', 'flut', 'flood', 'unwetter', 'regen', 'rain']
SEARCH_N_KEYWORDS = 1
SEARCH_W_REGEX = '.*(hamburg).*'
SEARCH_B_REGEX = '.*(berlin).*'
SEARCH_LOOK_BACK = 7    # how many days to look back

def save_posts(posts: list):
    """Save the posts to the database"""

    engine, session = autoconnect_db()

    # count how many posts were saved
    counter = 0

    for json_post in posts:

        # get the post identifier
        # this is the id the respective platform uses to identify the post
        identifier = json_post['id']

        # check if the post already exists
        existing_post = session.query(Report).filter(Report.identifier == identifier).first()

        # skip if the post already exists
        if existing_post:
            continue

        # convert the time field into a datetime object
        timestamp = datetime.fromisoformat(json_post['timestamp'])

        platform = json_post['platform']

        text_field_key = TEXT_FIELD[platform]
        text = json_post[text_field_key]

        # special formatting for RSS feeds
        # i.e. instead of 'rss', save 'rss/ndr'
        if platform == 'rss':
            platform = f'rss/{json_post["feed"]}'

        # create a new post object
        report = Report(
            identifier=identifier,
            text=text,
            url=json_post['url'],
            platform=platform,
            timestamp=timestamp,
            event_type=json_post['event_type']
        )

        # add the post to the session
        session.add(report)

        counter += 1

    # commit and close the session
    session.commit()
    session.close()

    return counter

def search_posts() -> list:
    """Request posts from the previous week with the specified search parameters."""

    # get todays date
    today = datetime.now()

    # get the date from LOOK_BACK days ago
    since = today - timedelta(days=SEARCH_LOOK_BACK)

    # Define the request payload
    payload = {
        'query': SEARCH_QUERY,
        'since': since.strftime('%Y-%m-%d'),
        'until': today.strftime('%Y-%m-%d'),
        'limit': SEARCH_LIMIT,
        'subreddits': SEARCH_SUBREDDITS,
        'platforms': SEARCH_PLATFORMS,
        'mandatory_keywords': SEARCH_MANDATORY_KEYWORDS,
        'optional_keywords': SEARCH_OPTIONAL_KEYWORDS,
        'n_keywords': SEARCH_N_KEYWORDS,
        'w_regex': SEARCH_W_REGEX,
        'b_regex': SEARCH_B_REGEX
    }

    # Send a POST request
    response = requests.post(API_URL, json=payload)

    # Handle the response
    if response.status_code == 200:
        results = response.json()['results']

        return results
    else:
        print('Error:', response.status_code, response.text)

        return []

def classify_post(json_post: dict) -> str:

    # TODO: connect to classifier when ready
    # for now, this just a random value

    # return a random value from this list
    class_list = ['other', 'storm', 'flood', 'rain']

    return random.choice(class_list)

def classify_posts(posts):

    classified_posts = []

    for post in posts:

        # add the class to the post
        post['event_type'] = classify_post(post)
        classified_posts.append(post)
    
    return classified_posts

if __name__ == '__main__':

    # an initial sleep, because the api might not be ready yet
    print(f'Waiting for the API to be ready. Sleeping for {TIMEOUT_DELAY} seconds')
    time.sleep(30)

    while True:

        if VERBOSE: print('Requesting... ', flush=True)
        posts = search_posts()

        if VERBOSE: print('Classifying... ', flush=True)
        posts = classify_posts(posts)

        if VERBOSE: print('Saving... ', flush=True)
        saved_counter = save_posts(posts)
        if VERBOSE: print(f'Saved {saved_counter} posts', flush=True)

        if VERBOSE: print(f'Done! Waiting for {REQUEST_DELAY} seconds', flush=True)
        time.sleep(REQUEST_DELAY)