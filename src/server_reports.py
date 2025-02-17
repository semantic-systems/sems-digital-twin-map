import requests
import json
import time
from datetime import datetime, timedelta

# where to save the file
SAVE_PATH = 'data/posts.json'

# how long to wait between requests (in seconds)
REQUEST_DELAY = 60 * 60 * 6    # 6 hours

# how long to wait before timing out a request (in seconds)
TIMEOUT_DELAY = 60             # 1 minute

# set to True to print more information
VERBOSE = True

# user agent for the requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Define the API URL (assuming the FastAPI server is running on localhost:5000)
API_URL = 'http://host.docker.internal:5000/search'

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
SEARCH_LOOK_BACK = 7

def write_output_json(data):

    with open(SAVE_PATH, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=4, ensure_ascii=False))

def search() -> list:
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



if __name__ == '__main__':

    while True:

        if VERBOSE: print('Requesting... ', end='', flush=True)

        posts = search()
        write_output_json(posts)

        if VERBOSE: print('Waiting for', REQUEST_DELAY, 'seconds', flush=True)

        time.sleep(REQUEST_DELAY)